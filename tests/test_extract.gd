extends SceneTree
## 端到端校验导出的第 1 章内容能按约定的 schema 被读取。
##
## 这不是「逻辑正确性」测试（那要用 ROM 对拍），而是防止导出管线
## 静默产出结构错误的数据：字段缺失、网格长度不匹配、tileset 引用失效。
##
## 运行：
## ```bash
## godot --headless --path . -s tests/test_extract.gd
## ```

const CHAPTER_DIR := "res://data/fe6/ch01"
const TILESET_TRES := "res://assets/tiles/mapasset01/tileset.tres"
const METATILE_COUNT := 1024

var _checks := 0
var _failures := 0


func _initialize() -> void:
	_check_tileset()
	_check_map()
	_check_units()
	_check_events()
	_check_texts()
	_check_chapter()

	print("extract: %d 项检查, %d 项失败" % [_checks, _failures])
	quit(1 if _failures > 0 else 0)


func _read_json(name: String) -> Dictionary:
	var path := ProjectSettings.globalize_path("%s/%s" % [CHAPTER_DIR, name])
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		_fail("%s 读不到" % name)
		return {}
	var parsed = JSON.parse_string(file.get_as_text())
	if not parsed is Dictionary:
		_fail("%s 不是 JSON 对象" % name)
		return {}
	return parsed


func _check_tileset() -> void:
	var tileset = load(TILESET_TRES)
	_check("tileset 能加载", tileset != null)
	if tileset == null:
		return
	_check("tileset 只有一个 source", tileset.get_source_count(), 1)
	var source = tileset.get_source(0)
	_check("atlas 图块数", source.get_tiles_count(), METATILE_COUNT)
	_check("tile 尺寸", tileset.tile_size, Vector2i(16, 16))


func _check_map() -> void:
	var map := _read_json("map.json")
	if map.is_empty():
		return
	var width: int = map.get("width", 0)
	var height: int = map.get("height", 0)
	var metatile: Array = map.get("metatile", [])
	var terrain: Array = map.get("terrain", [])
	_check("第 1 章宽 18", width, 18)
	_check("第 1 章高 21", height, 21)
	_check("metatile 网格长度", metatile.size(), width * height)
	_check("terrain 网格长度", terrain.size(), width * height)
	_check("metatile id 在范围内", metatile.filter(func(v): return int(v) < 0 or int(v) >= METATILE_COUNT).size(), 0)
	_check("terrain 名表非空", map.get("terrain_names", {}).size() > 0)


func _check_units() -> void:
	var data := _read_json("units.json")
	if data.is_empty():
		return
	var tables: Dictionary = data.get("tables", {})
	_check("8 个单位表", tables.size(), 8)
	var roy_table: Array = tables.get("UnitInfo_Chapter1_BlueA", [])
	_check("BlueA 有 2 人", roy_table.size(), 2)
	if roy_table.size() >= 1:
		# 设计稿：Roy 从 (4,20) 走到 (5,18)；坐标必须与 ch1-map.md 一致
		_check("Roy 入场坐标", _ints([roy_table[0].get("x_load"), roy_table[0].get("y_load")]), [4, 20])
		_check("Roy 落位坐标", _ints([roy_table[0].get("x_move"), roy_table[0].get("y_move")]), [5, 18])
		_check("Roy 武器", roy_table[0].get("items"), ["IID_RAPIER", "IID_VULNERARY"])

	var wiring: Dictionary = data.get("wiring", {})
	_check("挂接：我方初始单位表", wiring.get("units_blue"), "UnitInfo_Chapter1_BlueA")
	_check("挂接：回合事件表", wiring.get("event_list_turn"), "EventListScr_Chapter1_Turn")


func _check_events() -> void:
	var data := _read_json("events.json")
	if data.is_empty():
		return
	var scripts: Dictionary = data.get("event_scripts", {})
	var lists: Dictionary = data.get("event_lists", {})
	_check("11 个事件脚本", scripts.size(), 11)
	_check("4 个事件列表", lists.size(), 4)

	var opening: Array = scripts.get("EventScr_Chapter1_Opening", [])
	_check("开场脚本非空", opening.size() > 0)
	if opening.size() > 0:
		_check("开场第一条", opening[0].get("op"), "UnitCameraOff")
		_check("开场最后一条", opening[-1].get("op"), "End")
	var camera_ops := opening.filter(func(op): return op.get("op") == "Camera")
	_check("开场有运镜", camera_ops.size(), 1)
	if camera_ops.size() == 1:
		_check("运镜目标", _ints(camera_ops[0].get("args")), [11, 12])

	var turn_list: Array = lists.get("EventListScr_Chapter1_Turn", [])
	var turn_ops := turn_list.filter(func(op): return op.get("op") == "ListTurn")
	_check("回合事件 5 条", turn_ops.size(), 5)


func _check_texts() -> void:
	var data := _read_json("texts.json")
	if data.is_empty():
		return
	_check("19 条文本", data.get("count"), 19)
	var entries: Array = data.get("entries", [])
	_check("文本条数与 entries 一致", entries.size(), data.get("count"))
	if entries.size() > 0:
		_check("文本 id 形如 MSG_xxx", String(entries[0].get("id", "")).begins_with("MSG_"), true)


func _check_chapter() -> void:
	var data := _read_json("chapter.json")
	if data.is_empty():
		return
	_check("章节符号", data.get("symbol"), "CHAPTER_1")
	_check("章节序号", data.get("index"), 1)
	var meta: Dictionary = data.get("meta", {})
	_check("相机初始 x", meta.get("coord_x"), 9)
	_check("相机初始 y", meta.get("coord_y"), 4)
	_check("无需准备画面", meta.get("has_prep"), false)
	var counts: Dictionary = data.get("counts", {})
	_check("counts.metatiles", counts.get("metatiles"), METATILE_COUNT)


## JSON 里的数字都是 float，比较前必须转回 int，否则 [4.0] != [4]。
func _ints(values: Array) -> Array:
	return values.map(func(v): return int(v))


func _check(label: String, actual, expected = true) -> void:
	_checks += 1
	if actual != expected:
		_failures += 1
		printerr("FAIL %s: 实际 %s, 期望 %s" % [label, actual, expected])


func _fail(message: String) -> void:
	_checks += 1
	_failures += 1
	printerr("FAIL " + message)
