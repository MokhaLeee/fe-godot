extends SceneTree
## `core/rng.gd` 的黄金向量对拍。
##
## 运行：
## ```bash
## godot --headless --path . -s tests/test_rng.gd
## ```
## 黄金向量来自 `tools/gen_rng_golden.py`（同一份 C 算法的 Python 重写）。

const GOLDEN_PATH := "res://tests/golden/rng.json"
const RngScript := preload("res://core/rng.gd")

var _checks := 0
var _failures := 0


func _initialize() -> void:
	var golden := _load_golden()
	if golden.is_empty():
		quit(1)
		return

	_check_init_table(golden)
	for case in golden["cases"]:
		_check_seed(case)
	for case in golden["burn_cases"]:
		_check_seed(case)
	_check_range(golden["range"])
	_check_roll(golden["roll"])
	_check_lcg(golden["lcg"])
	_check_state_roundtrip()

	print("rng: %d 项检查, %d 项失败" % [_checks, _failures])
	quit(1 if _failures > 0 else 0)


func _load_golden() -> Dictionary:
	var path := ProjectSettings.globalize_path(GOLDEN_PATH)
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		printerr("找不到黄金向量: %s（先跑 python3 tools/gen_rng_golden.py）" % GOLDEN_PATH)
		return {}
	var parsed = JSON.parse_string(file.get_as_text())
	if not parsed is Dictionary:
		printerr("黄金向量不是 JSON 对象: %s" % GOLDEN_PATH)
		return {}
	return parsed


func _check_init_table(golden: Dictionary) -> void:
	var expected: Array = golden["init_table"]
	for i in expected.size():
		_expect("init_table[%d]" % i, RngScript.INIT_TABLE[i], int(expected[i]))


func _check_seed(case: Dictionary) -> void:
	var seed := int(case["seed"])
	var rng = RngScript.new(seed)

	var expected_state: Array = case["state_after_init"]
	for i in expected_state.size():
		_expect("seed %d state[%d]" % [seed, i], rng.get_state()[i], int(expected_state[i]))

	var expected_rn: Array = case["rn"]
	for i in expected_rn.size():
		_expect("seed %d rn[%d]" % [seed, i], rng.next_rn(), int(expected_rn[i]))


func _check_range(case: Dictionary) -> void:
	var seed := int(case["seed"])
	var max_value := int(case["max"])
	var rng = RngScript.new(seed)
	for i in case["values"].size():
		_expect("range %d[%d]" % [seed, i], rng.next_range(max_value), int(case["values"][i]))


func _check_roll(case: Dictionary) -> void:
	var seed := int(case["seed"])
	var threshold := int(case["threshold"])
	var rng = RngScript.new(seed)
	for i in case["values"].size():
		_expect("roll %d[%d]" % [seed, i], rng.roll(threshold), bool(case["values"][i]))
	for i in case["two_rn"].size():
		_expect("roll_2rn %d[%d]" % [seed, i], rng.roll_2rn(threshold), bool(case["two_rn"][i]))


func _check_lcg(case: Dictionary) -> void:
	var rng = RngScript.new()
	rng.rand_init_b(int(case["seed"]))
	for i in case["values"].size():
		_expect("lcg[%d]" % i, rng.next_b(), int(case["values"][i]))


func _check_state_roundtrip() -> void:
	var a = RngScript.new(4242)
	var saved: Array = a.get_state()
	var consumed := [a.next_rn(), a.next_rn(), a.next_rn()]

	var b = RngScript.new()
	b.set_state(saved)
	for i in consumed.size():
		_expect("状态往返[%d]" % i, b.next_rn(), consumed[i])


func _expect(label: String, actual, expected) -> void:
	_checks += 1
	if actual != expected:
		_failures += 1
		printerr("FAIL %s: 实际 %s, 期望 %s" % [label, actual, expected])
