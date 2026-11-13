class_name Rng
extends RefCounted
## FE6 随机数发生器（`src/Common/sys/random.c` 的逐位移植）。
##
## 两个独立子系统：
## - 三字状态的多项式 RN（`NextRN`）：战斗、成长、判定都用它
## - 32 位 LCG（`RandNextB`）：备用
##
## 移植要点：C 里 `u16` 的溢出截断必须**显式**复现。GDScript 的 int 是 64 位，
## 少写一个 `& 0xFFFF` 就会让整条序列漂掉，而且很难从结果上看出来。
##
## 正确性由 `tests/test_rng.gd` 对照 `tests/golden/rng.json` 校验；
## 黄金向量由 `tools/gen_rng_golden.py` 按同一份 C 算法生成。

const U16_MAX := 0xFFFF
const U32_MASK := 0xFFFFFFFF

## `random.c` 里的 init_table，8 个 16 位初值
const INIT_TABLE: Array[int] = [
	0xA36E, 0x924E, 0xB784, 0x4F67,
	0x8092, 0x592D, 0x8E70, 0xA794,
]

var _state: Array[int] = [0, 0, 0]
var _lcg: int = 0


func _init(seed: int = -1) -> void:
	if seed >= 0:
		rand_init(seed)


## `RandInit`：按 seed 选 3 个初值，再烧掉 seed % 23 个 RN。
func rand_init(seed: int) -> void:
	var i := posmod(seed, 7)
	_state[0] = INIT_TABLE[i & 7]
	i += 1
	_state[1] = INIT_TABLE[i & 7]
	i += 1
	_state[2] = INIT_TABLE[i & 7]

	var burn := posmod(seed, 23)
	for _n in burn:
		next_rn()


## `RandSetSt` / `RandGetSt`
func get_state() -> Array[int]:
	return [_state[0], _state[1], _state[2]]


func set_state(state: Array) -> void:
	_state[0] = int(state[0]) & U16_MAX
	_state[1] = int(state[1]) & U16_MAX
	_state[2] = int(state[2]) & U16_MAX


## `NextRN`：返回 0..65535
func next_rn() -> int:
	var rn := ((_state[1] << 11) + (_state[0] >> 5)) & U16_MAX

	var s2 := (_state[2] << 1) & U16_MAX
	if _state[1] & 0x8000:
		s2 = (s2 + 1) & U16_MAX

	rn ^= s2

	_state[2] = _state[1]
	_state[1] = _state[0]
	_state[0] = rn
	return rn


## `RandNext`：0 .. max_value-1（原版取整 bug 一并保留）
func next_range(max_value: int) -> int:
	@warning_ignore("integer_division")
	return (next_rn() * max_value) / 65535


## `RandNext_100`：0..99
func next_100() -> int:
	return next_range(100)


## `RandRoll`：`threshold > RandNext_100()`，注意是严格大于
func roll(threshold: int) -> bool:
	return threshold > next_100()


## `RandRoll2Rn`：两次取平均
func roll_2rn(threshold: int) -> bool:
	var value := next_100() + next_100()
	@warning_ignore("integer_division")
	value = value / 2
	return threshold > value


## `RandInitB`：备用 LCG 的种子
func rand_init_b(seed: int) -> void:
	_lcg = seed & U32_MASK


## `RandNextB`：32 位 LCG，返回 0..0xFFFFFFFF
func next_b() -> int:
	var value := ((_lcg << 2) + 2) & U32_MASK
	value = (value * (value + 1)) & U32_MASK
	value = value >> 2
	_lcg = value
	return value
