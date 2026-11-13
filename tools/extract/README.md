# tools/extract —— fe6-rebuild → Godot 内容管线

把 `~/fe6-rebuild` 里的 C 数据表、地图、事件脚本、文本导出成 Godot 能直接读的
JSON / PNG / `.tres`。**这里只读源码、只产数据，不含游戏逻辑。**

## 用法

```bash
# 需要 fe6-rebuild 的工作副本；默认路径 ~/fe6-rebuild，可用 FE6_ROOT 覆盖
python3 tools/extract_chapter.py --chapter 1
python3 tools/extract_chapter.py --chapter 1 --check   # 只校验，不写盘（CI 用）

python3 tools/gen_rng_golden.py                        # 生成 RNG 黄金向量
```

也可以走构建封装：

```bash
python3 tools/build.py extract   # 导出一章
python3 tools/build.py check     # 校验所有生成物是否最新
python3 tools/build.py test      # 跑 tests/*.gd
```

## 产出

| 文件 | 内容 | 消费方 |
|---|---|---|
| `data/fe6/chNN/map.json` | `width/height` + `metatile[]` + `terrain[]` + 地形名表 | `core/grid.gd`、TileMapLayer |
| `data/fe6/chNN/units.json` | `UnitInfo[]` 各表 + `ChapterEventInfo` 挂接 | `core/battle_state.gd` |
| `data/fe6/chNN/events.json` | `EventScr` / `EventListScr` / `MoveScr` 指令流 | `core/event_vm.gd` |
| `data/fe6/chNN/texts.json` | 本章对白（保留原版控制码） | `core/dialogue.gd` |
| `data/fe6/chNN/chapter.json` | 相机起点、tileset、BGM、胜利条件文本 id | 章节加载器 |
| `data/fe6/symbols.json` | 名字 ↔ 整数（`PID_*`、`IID_*`、`MSG_*`、`TERRAIN_*`…） | 所有消费方 |
| `assets/tiles/mapasset01/atlas.png` | 1024 个 16×16 metatile 的图集（32 列） | TileSet |
| `assets/tiles/mapasset01/metatiles.json` | 每个 metatile 的 4 个 tile 引用 + 地形 id | 3D 瓦片映射 |
| `assets/tiles/mapasset01/tileset.tres` | 现成的 `TileSet`（1024 个 tile 已注册） | `TileMapLayer` |
| `data/fe6/chNN/preview.png` | 2 倍地图预览，用来肉眼查地形 | 人工检查 |

## 约定与坑

**1. 事件脚本的真源是 `events/`，不是 `event_scripts/`。**
后者 45 个文件全被声明成弱符号（`arm-none-eabi-nm` 里显示 `V`），链接时被
`events/` 的强符号覆盖；坐标也是旧版的。用错了会拿到整体偏 3 列的旧地图。

**2. JSON 里的数字读进来是 `float`。**
Godot 的 JSON 解析器不区分整数，比较前必须 `int()`。`tests/test_extract.gd`
里 `_ints()` 就是干这个的。

**3. 地形 id 来自 tileset 的 LUT，不是章节数据。**
`TsaConf.dmp` 后 1024 字节是「每个 metatile 一个 terrain id」。地图格子只存
metatile id，地形靠查表。同一 terrain id 可能有多个别名，导出时按字母序取第一个。

**4. `tileset.tres` 是生成物，不要手改。**
1024 个 tile 是机械注册的；改图集要重跑导出，否则 tile 会错位。

**5. `.dmp` 是构建中间产物。**
源码是 `contents/maps/*/MapTsa_*.c`，`.dmp` 由 `make` 生成。本工具读 `.dmp`
（省掉再写一个 C 初始化器解析器）；如果 `.dmp` 缺失，先在 fe6-rebuild 里 `make all`。

## 校验

```bash
python3 tools/extract_chapter.py --check   # 生成物与源码一致
godot --headless --path . -s tests/test_extract.gd
```

`test_extract.gd` 校验 schema（网格长度、tile 数、字段存在、坐标与设计稿一致），
**不校验数值正确性** —— 那要靠 ROM 对拍（M1 用 `tools/emu/gbarun` 做）。
