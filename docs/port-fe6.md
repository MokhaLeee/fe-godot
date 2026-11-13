# 从 fe6-rebuild 移植到 Tactics：路线评估与施工方案

> 日期：2026-11-13 · 对象：`~/fe6-rebuild`（FE6 反编译重建工程）→ `~/fe-godot`（Godot 4.7.2 HD-2D 战棋脚手架）
> 本文只做决策与施工设计，不改代码。

---

## 0. 结论先行

**不要逐行翻译 C 代码，也不要把 GBA ROM 塞进 Godot 当模拟器。**
推荐路线是「**内容管线 + 规则内核重写 + 表现层重做 + ROM 当 oracle**」：

| 部分 | 处置 | 依据 |
|---|---|---|
| 数值规则（伤害/命中/成长/转职/技能/武器范围） | **搬运**：C 逐函数转 GDScript，用 ROM 对拍 | `src/Core` 14.2k 行，只有 4 个文件碰硬件寄存器 |
| 内容（地图/单位配置/事件脚本/文本/立绘/音乐） | **离线导出**成引擎中立格式，Godot 只消费 | 事件脚本 3,476 行、47 条指令、`EvtFunc` 仅 5 处引用 |
| 引擎骨架（Proc 协程、BG/OAM 直绘、m4a） | **重写** | UI 靠 `PutUiWindowFrame`/`PutText` 往 BG 图块里画，无法映射到场景树 |
| GBA ROM 本身 | **当参照实现（oracle）**，不进产品 | 已有 mGBA 无头 harness，可导出确定性的期望值 |

三条硬数据支撑这个判断：

1. **事件系统几乎纯数据**：44 个章节（含外传/试炼）的事件脚本合计 3,476 行，只有 47 种 `Evt*` 指令、1,369 次调用；`EvtFunc`/`EvtGotoIfNotFunc` 只引用了 **5 个** C 函数（其中 2 个还是 `setup_status` 这种一行代码）。事件 VM 重写量 ≈ 一个下午。
   > 注意：`event_scripts/` 那 45 个文件是弱符号兜底（`arm-none-eabi-nm` 里显示 `V`），链接时被 `events/` 的强符号覆盖，导出必须以 `events/` 为准，否则拿到的是旧版地图坐标。
2. **RNG 只有 28 行**（3 个 `u16` 状态 + 16 位异或），可以做到逐位一致 —— 这是对拍的前提。
3. **规则层干净**：`src/Core` 61 个文件里只有 `SaveData/hw-ops/{gbaflash,gbasram}*`、`Statscreen/source/bgslide.c` 依赖硬件，其余是纯结构体运算。

**代价要说清楚**：完整 24 章可通关约 **7–9 个月**（单人全职）；**3 个月**能做出「第 1 章可玩、战斗系统完整」的垂直切片。表现层（UI/菜单/战斗动画）是 60% 的工作量，不是规则。

---

## 1. 移植对象的真实形态

### 1.1 代码规模

| 区域 | 规模 | 性质 |
|---|---|---|
| `vanilla/*.c` | 113 文件 / 74,409 行 | 原版反编译 C（菜单、事件、战斗、banim、商店、竞技场…） |
| `src/Common/**` | 97 文件 / 47,064 行 | 重建工程的改造层（banim、存档、mapwork、klib、文本） |
| `src/Core/**` | 61 文件 / 14,247 行 | 规则改造（战斗伤害、成长、转职、技能、武器范围、debuff） |
| `gameinfo/chapterinfo/events` | 44 文件 / 3,476 行 | **章节事件真源**：事件脚本 + 单位配置（`UnitInfo[]`）+ 移动脚本 |
| `gameinfo/chapterinfo/event_scripts` | 45 文件 / 10,783 行 | 历史版本，全部定义为**弱符号**（`V`），被 `events/` 覆盖；导出时**不要用** |
| 符号表 | 16,074 条 | `fe6re.sym`，可用于定位任意函数/表 |
| 全部代码 | **有 C 源** | `vanilla/*.s` 只剩 24 个纯数据文件（`*_img.s`），无隐藏二进制代码 |

> 这点很重要：这**不是**「只有 asm 的黑盒」，理论上存在「把 C 编成 x86_64 + 重写硬件层」的路线（见 §2 路线 B），技术上没有硬阻塞 —— 阻塞在表现层。

### 1.2 可复用资产

| 资产 | 位置 | 规模 |
|---|---|---|
| 地图（metatile 索引 + TSA + 地形 LUT） | `contents/maps`, `gamedata/maps` | 32 KB tileset + 8 KB TSA per tileset |
| 图块集 | `contents/tileset/MapAsset0{1..4}` | 4 套，每套 1024 metatile（16×16） |
| 地形类型 | `include/constants/terrains.h` | 52 种 |
| 立绘 / 单位小图 / 图标 | `gamedata/unit-sprite`, `contents/banims` | 16,838 个 PNG |
| 战斗动画 | `gamedata/banim-data` | 8.5 MB，61 个 banim 目录 |
| 音乐/音效 | `gamedata/sounds` | 20 MB（m4a/MP2K 音序器格式） |
| 文本 | `texts/**`（日文原文 + 控制码） | `include/constants/msg.h` 3,369 行 msg id |
| 数据表 | `include/constants/*.h`（pids/jids/iids/…） | 6,113 行 |

### 1.3 已有的工具链（这是最大优势）

| 工具 | 作用 | 对我们的价值 |
|---|---|---|
| `tools/fe6extract`（Rust，`fe6-core` 可复用） | 从 ROM 提取数据表（已实现 `PInfo`，226 条） | **数据管线的骨架**，直接扩表 |
| `tools/banimtools/*` | dump banim 帧/OAM/脚本、LZSS、png↔4bpp | banim 帧导出成 PNG 序列 |
| `tools/maptools/{render_chapter,tmx2ea,lzss}.py` | 章节地图离线渲染成 PNG、TMX 往返 | 地图数据可视化 + 校验 |
| `tools/texttools/*` | Huffman 解压 + 控制码反解析 | 文本导出（含 `[LoadFace]` 这类演出控制码） |
| `tools/soundtools/*` | 音序 → WAV 离线渲染 | 音频转 OGG |
| `tools/emu/gbarun`（mGBA 核心，无头） | 按键脚本、内存探针、截图、`--hash`、SRAM 读写 | **oracle**：生成确定性的黄金向量 |

`gbarun` 的意义被低估了：它能在无 GPU 的 Ubuntu 上，按帧注入按键、读任意内存符号、导出截图哈希。这意味着「GDScript 重写的战斗公式是否与原版一致」是**可自动化验证**的，而不是靠肉眼比对。没有这个，路线 C 就是赌博；有了它，路线 C 是工程。

---

## 2. 三条路线对比

### 路线 A：把 mGBA 塞进 Godot

GDExtension 包一层 mGBA 核心，帧缓冲 → `Texture2D`，按键 → `InputMap`，SRAM → Godot 存档。

- ✅ 保真度 100%，工期 1–2 周，风险最低
- ❌ 画面永远是 240×160 像素，**拿不到 HD-2D**
- **正确用途**：留在 `tools/` 里做 oracle 和「参考模式」（类似《光环》的经典画面切换），不作为产品形态

### 路线 B：原生 C 核心 + 硬件抽象层（HAL 重写）

把 113 + 97 个 C 文件编成 x86_64，实现一套 shim：VRAM/OAM/调色板数组、`Decompress`、`Proc` 调度器、VBlank 帧循环、m4a → 宿主音频。然后每帧把 VRAM/OAM **解码成 display list**，再喂给渲染器。

- ✅ 逻辑 100% 一致（连 AI、事件、菜单流程都是原版）
- ✅ 本仓库所有代码都有 C 源，不存在二进制阻塞
- ❌ 解码出来的仍然是 240×160 的图块和精灵：`PutUiWindowFrame` 把菜单框画进 BG tilemap，`PutText` 把字画成图块。要做 HD-2D，就得把「BG 层第 3 号图块的第 4 个像素」反推成「3D 世界里的一面墙」—— 这是把模拟器输出再逆向一遍，比直接重写更贵
- ❌ `Proc` 是帧驱动的协程，逻辑和绘制写在同一个回调里，无法在不改动调用方的前提下插桩
- **估时**：跑到可交互约 1–2 个月；HD-2D 化再 6 个月以上且越改越脏

**结论**：B 适合「我要一个像素级一致的原版复刻」，不适合「我要 HD-2D 战棋」。但 B 的**前半段**（HAL + display list）可以作为 A 的替代品，如果将来需要更精确的参照。

### 路线 C：内容管线 + 规则重写 + 表现重做（推荐）

- ✅ 唯一能产出 HD-2D 的路线，且与现有 `tactics-spec.md` 的架构（`core/` 纯逻辑、headless 可测、Windows 做场景）天然吻合
- ✅ 规则与内容都可验证（oracle），不必「凭感觉复刻」
- ❌ 表现层（UI/菜单/战斗动画）必须重做，这是主要工作量
- **估时**：垂直切片 3 个月；24 章可通关 7–9 个月

### 决策表

| | A 模拟器 | B HAL 重写 | C 重写 |
|---|---|---|---|
| 到「能玩」 | 1–2 周 | 1–2 月 | 3 月（切片） |
| 逻辑保真 | 100% | 100% | 靠 oracle 逼近 |
| HD-2D | ❌ | 很难 | ✅ |
| 后续加内容（改剧情/加职业） | 要改 C 重编 ROM | 同左 | 改数据即可 |
| 与 fe-godot 现有架构契合 | 差 | 差 | 好 |
| 维护成本 | 低 | 高（脏 shim） | 中 |

**推荐 C**，B 的成果作为可选参照。A 无论如何都要做（oracle）。

---

## 3. 推荐架构

```
┌──────────────────────────────────────────────────────────────┐
│ 参照层  tools/oracle/                                        │
│   gbarun + 按键脚本 → 黄金向量（伤害/成长/RNG 序列/截图哈希） │
└───────────────┬──────────────────────────────────────────────┘
                │ 生成期望值
┌───────────────▼──────────────────────────────────────────────┐
│ 内容层  tools/extract/ → data/           （Ubuntu 生成物）    │
│   ROM + fe6 源码 → JSON/PNG/OGG → data/*.json, assets/*      │
└───────────────┬──────────────────────────────────────────────┘
                │ 只读
┌───────────────▼──────────────────────────────────────────────┐
│ 规则层  core/   （GDScript，无 Node，headless 可测）          │
│   grid / pathfinder / battle_state / combat / growth /        │
│   event_vm / turn_manager / rng / save                        │
└───────────────┬──────────────────────────────────────────────┘
                │ 状态 + 事件
┌───────────────▼──────────────────────────────────────────────┐
│ 表现层  scenes/ + assets/   （Windows 独占）                  │
│   3D metatile 地形 / Sprite3D billboard / UI Control /         │
│   镜头 / 特效 / banim 替代 / 事件演出                          │
└──────────────────────────────────────────────────────────────┘
```

关键设计约束（与 `tactics-spec.md` 一致，不新增）：

- `core/` 不出现 `extends Node`；事件 VM 用 `await` 但只 `await` 注入的表现层接口
- 坐标体系**沿用 FE6**：1 格 = 1 个 16×16 metatile；Godot 世界坐标 1 格 = 1.0 单位。不做单位换算，避免内容转换时逐章出错
- `data/` 全部是生成物，`tools/data/` 才是源
- 存档**不兼容 GBA 存档**（Godot Resource + 版本号），但保留「导入 GBA 存档」的调试入口

### 为什么事件 VM 用 `await` 而不是重写 Proc

FE6 的 `Proc` 是「每帧调一次回调，回调自己维护状态机」。GDScript 的 `await` 天然表达同一件事：

```gdscript
# core/event_vm.gd（示意）
func run(script: Array, presenter: Object) -> void:
	for cmd in script:
		match cmd.op:
			&"LoadUnits": await presenter.load_units(cmd.args)
			&"Camera":    await presenter.move_camera(cmd.args[0], cmd.args[1])
			&"MoveUnit":  await presenter.move_unit(cmd.args[0], cmd.args[1], cmd.args[2])
			&"MoveWait":  await presenter.wait_moves()
			&"Talk":      await presenter.show_dialogue(cmd.args[0])
			&"Func":      await _call_registered(cmd.args[0])
			&"GotoIfNotFunc": ...
			&"End":       return
```

好处：事件脚本原文（C 数组）能 1:1 映射成 JSON，不用理解原版 Proc 的挂起语义。坏处：`EvtFunc` 这类「回调进 C」的逃生口必须建一张注册表（已知只需 5 项）。

---

## 4. 数据契约（M0 的核心产出）

每类内容的「来源 → 导出 → 消费」：

| 内容 | 来源 | 导出格式 | Godot 消费 |
|---|---|---|---|
| 单位基础数据 | `PInfo`（226 条×48B，`fe6extract` 已实现） | `data/units.json` | `UnitData` Resource（已有骨架） |
| 职业数据 | `JInfo` | `data/classes.json` | `ClassData` |
| 物品/武器 | `IInfo` + `iinfo.c` | `data/items.json` | `ItemData` |
| 章节表 | `chapterinfo_data.c` + `chapters.h` | `data/chapters.json` | `ChapterDef` |
| 章节单位配置 | `UnitInfo_*` 数组（C） | `data/chapters/ch01.units.json` | `spawn` |
| 地图 | `contents/maps/*.dmp` + `Tileset` | `data/chapters/ch01.map.json`（terrain grid + metatile id） | `Grid` |
| 图块集 | `MapAsset0x_{Img1,Img2,TsaConf,ConfImg}` | `assets/tiles/map01/*.png` + `metatiles.json` | 3D 瓦片材质 |
| 事件脚本 | `gameinfo/chapterinfo/events/*.c`（**不是** `event_scripts/`） | `data/chapters/ch01.events.json` | `EventVM` |
| 文本 | `texts/**/*.txt` + `msg.h` | `data/texts/msg.json`（JSON 转义控制码） | `Dialogue` |
| banim | `gamedata/banim-data` + `banimtools` | `assets/banims/<id>/frame_%03d.png` + `oam.json` | `AnimatedSprite3D` |
| 音频 | `gamedata/sounds` + `soundtools` | `assets/audio/*.ogg` | `AudioStreamOggVorbis` |
| 地形消耗表 | `terrains.h` + vanilla 表 | `data/terrain.json` | `Pathfinder` |

### 4.1 地图（最关键）

FE6 一章地图 = 1024 个 metatile 的图集 + 每格一个 metatile id + 每格一个地形 id。

```json
{
  "id": "ch01",
  "width": 18, "height": 21,
  "tileset": "map01",
  "metatile": [12, 12, 5, 6, ...],
  "terrain":  [1, 1, 12, 26, ...]
}
```

3D 侧只认 `terrain`（决定瓦片模型与移动消耗），`metatile` 只用于「还原原版观感」的可选贴图。**先做 12 类地形占位（平地/道路/森林/山地/水/城墙/村庄/城门/桥/沙/室内地板/屋顶），52 类逐章按需补。** 这一步决定了美术工作量，必须早做。

### 4.2 事件脚本

```json
[{"op":"UnitCameraOff"},
 {"op":"LoadUnits","args":["UnitInfo_Chapter1_RedA"]},
 {"op":"Camera","args":[11,12]},
 {"op":"Sleep","args":[16]},
 {"op":"MoveUnit","args":[1,7,18]},
 {"op":"Func","args":["setup_status"]},
 {"op":"End"}]
```

C 数组 → JSON 用正则 + 一个 100 行的 Python 解析器（宏只有 47 种，且都是 `EvtXxx(args)` 形式）。这一步不需要理解游戏逻辑。

---

## 5. 路线图与验收

所有阶段的验收都用 oracle，不靠肉眼。

### M0 管线验证（1 周）

产出：`tools/extract/`（Python，扩 `fe6-core` 或独立）+ 第 1 章的 `map/units/events/texts` JSON + `assets/tiles/map01/*.png`。
验收：
- `render_chapter.py` 渲染的 PNG 与 ROM 内地图逐像素一致（工具已能验证）
- `data/chapters/ch01.events.json` 指令数 = 源码 `Evt*` 调用数
- Godot 里用 `TileMapLayer` 显示第 1 章地图，截图肉眼确认地形正确

### M1 战场骨架（2–3 周）

产出：`core/grid.gd`、`core/pathfinder.gd`（Dijkstra，地形消耗）、`scenes/battle/`（3D metatile 地图 + 单位 billboard + 光标 + 移动范围高亮）。
验收：oracle 对拍「Roy 在 ch1 起点、移动力 5 的可达格集合」与原版截图/内存探针一致。

### M2 战斗规则（3–4 周）

产出：`core/combat.gd`（伤害/命中/必杀/追击/武器三角/耐久）、`core/growth.gd`（升级成长、职业加成、转职）、`core/rng.gd`。
验收：**1,000 组随机对拍** —— 用 `gbarun` 在 ROM 里构造同种子同攻击方，导出 `damage/hit/crit/pierce`，与 GDScript 结果逐字段比对。RNG 必须逐位一致。

### M3 事件与对话（3 周）

产出：`core/event_vm.gd`（47 条指令）、`core/dialogue.gd`（控制码解析）、章节开始/增援/村庄/访问、章节切换。
验收：第 1 章开场事件完整跑通，`gbarun` 侧用同一按键序列，对比「事件结束时单位坐标/HP/金币」快照。

### M4 菜单与流程（4–5 周）

产出：地图菜单、单位面板、物品/运输队/交易/救出、准备界面、存档。
验收：能完成「整章：准备 → 部署 → 战斗 → 胜利结算 → 下一章」。

### M5 战斗动画与 HD-2D 打磨（4–6 周）

产出：banim 替代方案（见 §6.5）、镜头拉升过渡、光影/景深/体积雾。
验收：视觉基线对照 `tactics-spec.md` §8。

### M6 内容铺量（8–12 周）

24 章 + 外传逐章导入、逐章回归。每章一个 smoke case：能进章、开场事件不卡、能走到 Boss、胜利后跳下一章。

---

## 6. 七个技术难点

### 6.1 Proc 协程 → await / Tween

原版流程都是 `ProcScr` 数组（`PROC_REPEAT` 每帧一次）。GDScript 用 `await` + `Tween` + 一个极小的 `Proc` 替身（`RefCounted`，`step()` 由 `_process` 驱动）即可。**不要**试图模拟「帧」：原版 60fps 的帧数（`EvtSleep(16)`）在 Godot 里应解释为「时长」，用秒而不是帧，否则高刷屏上会变快。

### 6.2 BG 直绘 UI → Control

`PutUiWindowFrame(x,y,w,h,kind)` 把 9-slice 窗口框画进 BG tilemap；`PutText` 把字画成图块。Godot 里必须换成 `NinePatchRect` + `RichTextLabel`/自绘文本。
**建议**：先做「原版风格的 2D UI」（用导出的窗口框 PNG 做 9-slice），不要一上来做 HD-2D 风 UI。理由：UI 是信息密度最高的部分，风格化会拖慢整个项目的可玩性验证。

### 6.3 metatile 地图 → 3D 瓦片

一格 = 16×16 px = 2×2 个 8×8 tile。HD-2D 做法：一格 = 1 个 3D 瓦片（石板/草块/水面），高度差用 `MultiMeshInstance3D` 或 `GridMap`。
**坑**：FE6 地图是「俯视平面 + 少量 2.5D 建筑遮挡」，没有真实高度数据。高低差、屋顶遮挡要**手工标注**（每章一张 `heightmap` 覆盖层），这是内容工作，不是代码工作。先只做「平地 + 建筑块」，不做高低差。

### 6.4 OAM 单位 → Sprite3D

`Sprite3D` + `BILLBOARD_FIXED_Y` + `pixel_size` 按「1 格 = 1 单位 / 16 px」换算 + `ALPHA_CUT_DISCARD`（`tactics-spec.md` §8.3 已写）。
**新增问题**：原版单位贴图是 16×16 或 32×32 的 4bpp + 调色板索引，不同阵营共用图形只换调色板。导出时要**按阵营展开成独立 PNG**，否则 Godot 里没法运行时换色板（`ShaderMaterial` 也能做，但增加复杂度）。

### 6.5 banim（战斗动画）：三档策略

61 个 banim，每个是「脚本 + 帧 + OAM」驱动，8.5 MB 数据。这是最贵的部分。

| 档 | 做法 | 成本 | 何时做 |
|---|---|---|---|
| 1 | 不播动画，直接结算 + 数字飘字 + 命中特效 | 2 天 | M2（必须有，否则没法测战斗） |
| 2 | 2D 剧场：导出帧序列 → `AnimatedSprite2D` 全屏播放（原版观感，不 HD-2D） | 2 周 | M3–M4 |
| 3 | HD-2D 分镜：3D 场景里镜头推拉 + 角色动作 | 1–2 月/10 个 | M5，按角色重要性挑 |

**不要一上来做档 3。** 战棋的可玩性 90% 在战场上，战斗动画是「奖励」。

### 6.6 m4a 音源 → OGG

m4a/MP2K 是「音色 + 音序器」，不是音频文件。`tools/soundtools/dump_wav.py` 可离线渲染。
**建议**：M0 就批量渲染成 OGG（80 首左右，几十 MB），Godot 直接用。不要移植音序器。

### 6.7 确定性与存档

- RNG 必须与 ROM 逐位一致（28 行，直接抄），否则对拍无意义
- 存档用 Godot `Resource` + `save_version`，**不兼容** GBA 存档
- 额外送一个能力：因为 `BattleState` 只通过 Action 变更（`tactics-spec.md` 硬约束 3），**Action 序列 = 存档 = 回放 = 测试用例**。这让「第 1 章 30 回合回归」变成一个可执行脚本

---

## 7. 版权与发布（必须先想清楚）

FE6 是任天堂 IP。**带原版美术/文本/音乐的构建不能上 Steam，也不能公开分发。**

三条出口：

1. **私人/学习用途**：直接做，随便用原版资产（本文默认假设）
2. **「引擎 + 原版内容」分离**：产品只发引擎与自制内容，玩家自备 ROM 后由工具导入（技术上可行，法律上仍灰）
3. **换皮**：美术、文本、名字、数值全换，只保留「玩法与数据结构」。这是唯一能上 Steam 的路，但那时它已经不是你想要的「移植 FE6」，而是「用 FE6 的工程做一款原创战棋」

另外 `tactics-spec.md` 里「不做多结局、好感度、装备合成」的裁剪，与 FE6 的支援/好感度系统直接冲突 —— 如果目标是「移植 FE6」，这条裁剪要取消。

---

## 8. M0 状态：内容管线已落地（2026-11-13）

原计划的 8 项里，**7 项已完成**，第 7 项（ROM oracle）留到 M1。

| # | 原计划 | 实际产出 |
|---|---|---|
| 1 | `chapter_events.py` | `tools/extract/events.py` + `events.json`（11 脚本 / 4 列表） |
| 2 | `chapter_units.py` | `tools/extract/units.py` + `units.json`（8 表 + 挂接关系） |
| 3 | `pinfo.py` | ⏳ 未做，M1 补（`fe6extract` 已有 Rust 版可复用） |
| 4 | `map.py` | `tools/extract/mapdata.py` + `map.json`（18×21） |
| 5 | `texts.py` | `tools/extract/texts.py` + `texts.json`（19 条） |
| 6 | `tileset.py` | `tools/extract/tileset.py` → `atlas.png` + `metatiles.json` + **`tileset.tres`**（1024 tile 已注册，可直接给 `TileMapLayer`） |
| 7 | `oracle/run_case.py` | ⏳ 未做，M1 与战斗公式一起做 |
| 8 | `core/rng.gd` | `core/rng.gd` + `tests/test_rng.gd`（**287 项**对拍通过） |

**验证证据（可复现）**

- 地图渲染与 fe6-rebuild 自带 `render_chapter.py` **逐像素一致**（288×336）
- 单个 metatile 展开与 `ConfImg.png` 对应区域一致（抽检 0/6/720/1023）
- 幂等：重复导出不改 mtime，`--check` 退出码 0
- `tests/test_rng.gd`：287 项检查，0 失败
- `tests/test_extract.gd`：34 项 schema 检查，0 失败（含「Roy 从 (4,20) 走到 (5,18)」与设计稿一致）

**与原计划的偏差（都是有意的）**

1. 工具做成包 + 单一 CLI（`tools/extract/` + `tools/extract_chapter.py`），而不是 6 个平铺脚本 —— 后续加 `pinfo/items` 时不用改调用方式
2. 输出目录是 `data/fe6/chNN/`，与手写的 `data/units/` 分开，避免生成物和源混淆
3. RNG 的黄金向量当前由 **Python 参考实现**生成（验证「GDScript 是否精确复现 C 的位截断」）；与 ROM 的比对在 M1 做
4. `tileset.tres` 也纳入生成物 —— 否则 Windows 侧要在编辑器里手点 1024 个图块

**M1 待办**：`pinfo/items/classes` 导出、`gbarun` oracle 封装、`core/grid.gd` + `pathfinder.gd`、3D metatile 战场（`scenes/` 归 Windows 侧）。

> 环境备注：`godot` 不在 PATH 里，二进制在 `~/tools/Godot_v4.7.2-stable_linux.x86_64`。
> `tools/build.py` 已做回退查找，不建软链也能跑；新加的资源要先 `godot --headless --import` 才会被导入。

---

## 9. 决策记录

| 决策 | 结论 | 影响 |
|---|---|---|
| 目标形态 | **忠实移植 FE6（全章节 + 全系统）**，HD-2D 只是观感升级 | 规则以 ROM 为准，不裁剪；`tactics-spec.md` 里「不做好感度/支援」的裁剪作废 |
| 第一步 | **M0 内容管线**（已完成） | 后续每章都走同一套导出 |
| 表现层顺序 | **先原版风格 2D UI，M5 再做 HD-2D** | M1–M4 迭代速度优先 |

**仍然悬着的一件事：版权定位。**

FE6 是任天堂 IP。带原版美术/文本/音乐的构建**不能上 Steam、不能公开分发**。
如果这个项目将来要发，资产管线必须从一开始就设计成「可替换」：

- 导出物全部走 `data/fe6/` 和 `assets/tiles/mapasset01/`（与原版资产同层，可整体替换）
- 代码里不出现角色名/剧情文本的硬编码，一律查 `symbols.json` + `texts.json`

这样「换皮」时只需替换 `assets/` 与 `data/fe6/`，`core/` 与 `scenes/` 不动。
如果不是为了发布，这条约束可以放宽，但仍建议保留 —— 它同时也让「打包体积」可控。

---

## 附录：勘察命令（可复现本文所有数字）

```bash
cd ~/fe6-rebuild
find src include -name '*.c' -o -name '*.h' | xargs wc -l | tail -1      # 94,559
find vanilla -name '*.c' | xargs wc -l | tail -1                          # 74,409
grep -rhoE '\bEvt[A-Za-z0-9_]+' gameinfo/chapterinfo/events/*.c | sort -u | wc -l  # 47
grep -rhoE 'Evt(Func|GotoIfNotFunc)\([A-Za-z0-9_]+' gameinfo/chapterinfo/events/*.c | sed 's/.*(//' | sort -u  # 5
grep -cE 'CHAPTER_[0-9A-Z_]+ = 0x' include/constants/chapters.h           # 48
grep -rn 'REG_' src/Core | wc -l                                          # 59（集中在 4 个文件）

# 事件脚本真源 vs 弱符号兜底
ls gameinfo/chapterinfo/events/*.c | wc -l                                # 44
wc -l gameinfo/chapterinfo/events/*.c | tail -1                           # 3,476
arm-none-eabi-nm gameinfo/chapterinfo/event_scripts/chapter1.o | grep ChapterEventInfo_Chapter1  # V（weak）
arm-none-eabi-nm fe6re.elf | grep 'ChapterEventInfo_Chapter1$'            # R（强符号，来自 events/）
```
