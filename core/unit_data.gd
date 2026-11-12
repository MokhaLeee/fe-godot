class_name UnitData
extends Resource
## 单位的静态定义。运行时实例用 UnitInstance（阶段 1 引入）。
## 本文件只做数据契约，不含战斗逻辑。

@export var id: StringName = &""
@export var display_name: String = ""

@export_group("Stats")
@export var max_hp: int = 20
@export var attack: int = 5
@export var defense: int = 2
@export var move_points: int = 4
@export var attack_range_min: int = 1
@export var attack_range_max: int = 1

@export_group("Movement")
## foot / horse / fly，决定地形消耗表
@export var move_type: StringName = &"foot"

@export_group("Visual")
## 像素精灵：单帧 32×32，Sprite3D 用 ALPHA_CUT_DISCARD 投阴影
@export var sprite_path: String = ""
@export var portrait_path: String = ""
