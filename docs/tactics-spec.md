# 像素 HD-2D 战棋 · 项目规格

> **这一份文档取代之前的 `onboarding.md`、`windows-ubuntu-workflow.md`、`ubuntu-scaffold-spec.md`。**
> 项目尚未开工，故直接按最新需求（HD-2D：3D 地图 + 像素角色）从头定义。

| | |
|---|---|
| 项目代号 | Tactics（自行替换） |
| 类型 | 回合制战棋（SRPG）× HD-2D 探索 |
| 视觉 | 3D 低多边形地图 + 2D 像素角色（billboard） |
| 目标平台 | Windows（Steam），兼顾 Linux / Steam Deck |
| 开发形态 | Ubuntu Server 写逻辑与构建，Windows 跑编辑器做视觉 |
| 引擎 | Godot 4.7.2 stable，Forward+ 渲染器 |
| 作者背景 | C / Python 熟练 |

**怎么用这份文档**

- 第 1–4 节：供你阅读，回答「做什么、为什么这么选、两台机器怎么配合」
- 第 5–7 节：**施工规格**，整份交给 Ubuntu 工作区 agent 执行
- 第 8 节：HD-2D 的技术实现细节，做视觉时翻
- 第 9–10 节：路线图与坑清单

---

## 1. 项目定义

一个「探索 + 战斗」双模式的像素战棋。玩家在 3D 场景中操控像素小人走动、触发事件，遇敌后切到战棋模式，在同一张 3D 地图上以格子为单位调动单位。

**视觉基准**：《三角战略》（Triangle Strategy）——同为 HD-2D + 战棋，是最贴近的参照物。
**玩法基准**：《火焰纹章》的战场节奏、《Into the Breach》的信息透明度。

**明确不做**（第一版）：多结局分支、角色好感度、装备合成、联机。

---

## 2. 技术选型

### 2.1 引擎：Godot 4.7.2

| 候选 | 结论 | 关键理由 |
|---|---|---|
| **Godot 4.7.2** | ✅ 采用 | Linux 原生、跨平台导出、HD-2D 够用、迭代秒级 |
| Unreal 5 | ❌ 排除 | 编辑器重度依赖 GPU，无独显的 Ubuntu Server 跑不动；Paper2D 多年维护模式，2D 精灵恰是弱项；空项目包体几百 MB；C++ 编译分钟级 |
| Unity | ❌ 排除 | Linux 编辑器功能滞后；IL2CPP 跨编 Windows 需 Windows 构建机 |
| MonoGame | ❌ 排除 | 要自造 UI、序列化、编辑器，对单人第一款商业项目是纯时间税 |

Godot 的 HD-2D 能力来自 Forward+ 渲染器：景深、体积雾、SSAO、动态光照都可用。它的「不如 UE 华丽」在「低多边形 + 手绘贴图 + 像素精灵」这种风格里几乎不构成劣势——这个风格的核心是美术统一，不是渲染技术。

### 2.2 语言分工

| 层 | 语言 | 说明 |
|---|---|---|
| 运行时逻辑、UI、场景 | **GDScript** | 语法接近 Python，迁移成本低 |
| 离线数据生产、数值模拟、构建 | **Python** | 生成 `.tres`、跑蒙特卡洛平衡、封装导出 |
| 性能热点 | GDExtension (C++) | **仅在 profiler 证明瓶颈后**启用 |

战棋是回合制，8×8～20×20 的地图跑 Dijkstra，GDScript 连 1% CPU 都用不到。**性能不是本项目的问题，不要提前优化。**

### 2.3 硬约束

1. **`core/` 下不允许 `extends Node`** —— 全部写成 `RefCounted` 或普通类。换来 headless 可测试。
2. **Godot 版本锁 4.7.2** —— 两端一致，否则 `.uid` 漂移。
3. **`BattleState` 只通过 `Action` 对象变更** —— 保存 Action 序列 = 存档 + 回放 + 调试。
4. **`scenes/` 由 Windows 侧独占编辑** —— 避免 `.tscn` 冲突。

---

## 3. 开发环境形态

```
┌─────────────────────┐         ┌──────────────────────┐
│  Ubuntu Server       │  Git    │  Windows             │
│  · GDScript 逻辑      │ ◄─────► │  · Godot 编辑器       │
│  · headless 测试      │         │  · 搭场景 / 调 UI     │
│  · Python 数据生成     │         │  · HD-2D 视觉调试     │
│  · 导出构建           │         │  · 最终验收           │
└─────────────────────┘         └──────────────────────┘
```

**两套独立工作副本，Git 做唯一真源。** 不用 rsync 双向、不用网盘、不用 Samba 挂载——`.godot/` 缓存与 `.uid` 文件会因此损坏。

Server 无 GUI 完全够用：`godot --headless` 能跑测试、能导出、能生成资源。**唯一需要图形界面的是场景编辑与视觉调试，这部分交给 Windows。**

### 3.1 目录归属

| 路径 | 归属 | 理由 |
|---|---|---|
| `scenes/` | **Windows 独占** | 需拖拽、看布局、对像素 |
| `assets/` 视觉 | **Windows 独占** | 图集、动画、材质 |
| `core/` | **Ubuntu 独占** | 可 headless 测试 |
| `data/*.tres` | **Ubuntu 生成** | 生成物提交，Windows 只消费 |
| `tools/` | Ubuntu | Python |
| `tests/` | Ubuntu 主写 | |
| `project.godot` / `export_presets.cfg` | **改前告知** | 两边都依赖 |

**永远不要两边同时编辑同一个 `.tscn`。**

### 3.2 日常循环

两边开工第一件事：
```bash
git pull --rebase --autostash
```
两边收工最后一件事：
```bash
git push
```

Ubuntu 侧改逻辑：
```bash
godot --headless --path . -s addons/gut/gut_cmdln.gd -gdir=res://tests -gexit
```

Windows 侧改场景：编辑器里做，提交 `.tscn` 与 `.uid`。

### 3.3 冲突处理

`.tscn` 冲突**不要手改**：
```bash
git checkout --theirs scenes/battle.tscn
git add scenes/battle.tscn
```
然后回 Windows 编辑器重做本地那部分。

---

## 4. 目录结构

```
tactics/
├── .gitignore
├── .gitattributes
├── .editorconfig
├── project.godot
├── export_presets.cfg
├── README.md
├── core/                       # 纯逻辑，不依赖 Node
│   ├── unit_data.gd
│   ├── grid.gd                 # 阶段 1
│   ├── pathfinder.gd           # 阶段 1
│   ├── battle_state.gd         # 阶段 1
│   └── turn_manager.gd         # 阶段 1
├── data/
│   └── units/                  # gen_units.py 生成，提交
├── scenes/
│   ├── main.tscn               # 3D 骨架
│   ├── world/                  # 探索场景（Windows）
│   └── ui/                     # HUD（Windows）
├── assets/
│   ├── sprites/
│   ├── tiles/
│   └── audio/
├── tests/
├── tools/
│   ├── requirements.txt
│   ├── gen_units.py
│   ├── build.py
│   └── data/units/*.yaml
└── docs/
    └── workflow.md
```

---

## 5. 施工规格（交给 Ubuntu agent 执行）

### 5.0 执行指令

```
你是运行在 Ubuntu 上的开发环境初始化 agent。请严格按第 5 节创建文件：
1. 不添加任何未列出的游戏逻辑
2. 全部 UTF-8、LF 换行
3. 完成后执行第 7 节验收，逐条报 pass/fail
4. 失败先修再报，不要跳过
5. 第 8 节是背景资料，不需要执行
```

### 5.1 环境前提

```bash
sudo apt update
sudo apt install -y git git-lfs python3 python3-pip python3-venv unzip wget curl

mkdir -p ~/tools && cd ~/tools
wget -q https://github.com/godotengine/godot/releases/download/4.7.2-stable/Godot_v4.7.2-stable_linux.x86_64.zip
unzip -o Godot_v4.7.2-stable_linux.x86_64.zip
chmod +x Godot_v4.7.2-stable_linux.x86_64
sudo ln -sf ~/tools/Godot_v4.7.2-stable_linux.x86_64 /usr/local/bin/godot
godot --headless --version    # 期望 4.7.2.stable.official.<hash>
```

导出模板（需导包时）：
```bash
# 下载 Godot_v4.7.2-stable_export_templates.tpz
# 解压后把 templates/ 内容放入 ~/.local/share/godot/export_templates/4.7.2.stable/
```

> `forward_plus` 渲染器在 headless 下不渲染，无需 GPU。**导出本身不需要显卡**，只有运行游戏才需要。

### 5.2 `.gitignore`

```gitignore
# ── Godot 4 ────────────────────────────────
.godot/
/android/

# 导出产物
build/

# ── Python ─────────────────────────────────
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/

# ── 编辑器 / 系统 ──────────────────────────
.vscode/
.idea/
*.swp
*~
.DS_Store
Thumbs.db
```

> **不要**忽略 `*.uid`。Godot 4.4+ 的 `.uid` 旁挂文件必须进版本库。

### 5.3 `.gitattributes`

```gitattributes
* text=auto eol=lf

*.png binary
*.jpg binary
*.jpeg binary
*.webp binary
*.ogg binary
*.wav binary
*.mp3 binary
*.flac binary
*.ttf binary
*.otf binary
*.pck binary
*.exe binary
*.zip binary
*.glb binary
*.gltf binary

*.gd    text eol=lf
*.tscn  text eol=lf
*.tres  text eol=lf
*.cfg   text eol=lf
*.godot text eol=lf
```

### 5.4 `.editorconfig`

```editorconfig
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = space
indent_size = 2

[*.gd]
indent_style = tab
indent_size = 4

[*.py]
indent_style = space
indent_size = 4

[*.{yml,yaml}]
indent_style = space
indent_size = 2
```

### 5.5 `project.godot`

```ini
; Engine configuration file.
; HD-2D 配置：Forward+ 渲染器 + 原生分辨率 + Nearest 贴图过滤。
; 两端 Godot 版本必须一致（4.7.2）。

config_version=5

[application]

config/name="Tactics"
config/description="Pixel HD-2D tactical RPG"
run/main_scene="res://scenes/main.tscn"
config/features=PackedStringArray("4.7", "Forward Plus")

[display]

window/size/viewport_width=1280
window/size/viewport_height=720
window/size/window_width_override=1280
window/size/window_height_override=720
window/stretch/mode="canvas_items"
window/stretch/aspect="expand"

[rendering]

renderer/rendering_method="forward_plus"
renderer/rendering_method.mobile="mobile"
textures/default_filters/use_nearest_mipmap_filter=true
textures/canvas_textures/default_texture_filter=0
environment/defaults/default_clear_color=Color(0.05, 0.06, 0.09, 1)
anti_aliasing/quality/msaa_3d=0
```

**三处与纯 2D 方案不同，都是 HD-2D 的硬要求：**

| 配置 | 值 | 为什么 |
|---|---|---|
| `rendering_method` | `forward_plus` | 景深、体积雾、SSAO 只在 Forward+ 完整可用 |
| `viewport` | `1280×720` | HD-2D 是「高分辨率场景 + 低分辨率精灵」，**不整屏降采样** |
| `stretch/mode` | `canvas_items` | 3D 按原生分辨率渲染，只有 2D UI 随窗口缩放。用 `viewport` 会把 3D 一起降采样，景深全糊 |

`msaa_3d=0`：像素风不需要抗锯齿，开了反而让像素边缘发虚。

### 5.6 `export_presets.cfg`

```ini
[preset.0]

name="Windows Desktop"
platform="Windows Desktop"
runnable=true
advanced_options=false
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter=""
exclude_filter=""
export_path="build/windows/tactics.exe"
encryption_include_filters=""
encryption_exclude_filters=""
encrypt_pck=false
encrypt_directory=false
script_export_mode=2

[preset.0.options]

custom_template/debug=""
custom_template/release=""
debug/export_console_wrapper=1
binary_format/embed_pck=false
texture_format/s3tc_bptc=true
texture_format/etc2_astc=false
binary_format/architecture="x86_64"
application/modify_resources=false
application/product_name="Tactics"

[preset.1]

name="Linux/X11"
platform="Linux"
runnable=true
advanced_options=false
dedicated_server=false
custom_features=""
export_filter="all_resources"
include_filter=""
exclude_filter=""
export_path="build/linux/tactics.x86_64"
encryption_include_filters=""
encryption_exclude_filters=""
encrypt_pck=false
encrypt_directory=false
script_export_mode=2

[preset.1.options]

custom_template/debug=""
custom_template/release=""
debug/export_console_wrapper=1
binary_format/embed_pck=false
texture_format/s3tc_bptc=true
texture_format/etc2_astc=false
binary_format/architecture="x86_64"
```

> 最小字段集，缺失项由 Godot 用默认值填充。若首次导出报字段缺失，在编辑器 Export 对话框点一次 Save 让 Godot 补全后提交。`export_path` 必须保持相对路径。

### 5.7 `scenes/main.tscn`

阶段 0 的验证场景：3D 地面 + 相机 + 光照 + 一个方块占位。用 `position` + `rotation_degrees` 写，避免手算矩阵出错。

```ini
[gd_scene load_steps=3 format=3]

[sub_resource type="PlaneMesh" id="PlaneMesh_ground"]
size = Vector2(20, 20)

[sub_resource type="BoxMesh" id="BoxMesh_actor"]
size = Vector3(0.6, 1.2, 0.6)

[node name="Main" type="Node3D"]

[node name="Camera3D" type="Camera3D" parent="."]
position = Vector3(0, 3.2, 6)
rotation_degrees = Vector3(-28, 0, 0)
fov = 28.0

[node name="DirectionalLight3D" type="DirectionalLight3D" parent="."]
position = Vector3(3, 5, 2)
rotation_degrees = Vector3(-50, -25, 0)
shadow_enabled = true

[node name="WorldEnvironment" type="WorldEnvironment" parent="."]

[node name="Ground" type="MeshInstance3D" parent="."]
mesh = SubResource("PlaneMesh_ground")

[node name="Actor" type="MeshInstance3D" parent="."]
position = Vector3(0, 0.6, 0)
mesh = SubResource("BoxMesh_actor")
```

> **`fov = 28.0` 是 HD-2D 的关键**：小 FOV 压缩纵深，接近正交投影，是八方旅人/三角战略的观感来源。相机俯角约 28–35°。
> 若 Windows 侧打开后画面空白，选中 `Camera3D` 用编辑器 Look At 对准原点重新确认角度。

### 5.8 `core/unit_data.gd`

数据契约，不依赖 Node。

```gdscript
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
```

### 5.9 `tools/requirements.txt`

```text
PyYAML>=6.0
Pillow>=10.0
```

### 5.10 `tools/gen_units.py`

**必须幂等**：同样输入产生逐字节相同的输出。

```python
#!/usr/bin/env python3
"""YAML -> Godot 4 Resource (.tres) 生成器。

幂等保证：
  - 字段固定顺序输出
  - 浮点固定格式化
  - 不写时间戳、随机 id、绝对路径
  - 内容相同不写盘（保持 mtime 稳定）

用法:
  python3 tools/gen_units.py            # 生成到 data/units/
  python3 tools/gen_units.py --check    # 只校验不写盘（CI 用）
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("缺少依赖: pip install -r tools/requirements.txt")

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "tools" / "data" / "units"
OUT_DIR = ROOT / "data" / "units"

SCRIPT_PATH = "res://core/unit_data.gd"
SCRIPT_CLASS = "UnitData"

# 顺序必须与 core/unit_data.gd 的字段声明一致
FIELD_ORDER = [
    "id",
    "display_name",
    "max_hp",
    "attack",
    "defense",
    "move_points",
    "attack_range_min",
    "attack_range_max",
    "move_type",
    "sprite_path",
    "portrait_path",
]

HEADER = (
    '[gd_resource type="Resource" script_class="{cls}" '
    "load_steps=2 format=3]\n\n"
    '[ext_resource type="Script" path="{path}" id="1_script"]\n\n'
    "[resource]\n"
    'script = ExtResource("1_script")\n'
).format(cls=SCRIPT_CLASS, path=SCRIPT_PATH)


def fmt_scalar(value) -> str:
    """把 Python 值格式化为 Godot 字面量。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return f"{value:.6f}".rstrip("0").rstrip(".")
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        return "PackedStringArray(" + ", ".join(fmt_scalar(v) for v in value) + ")"
    raise TypeError(f"不支持的字段类型: {type(value)!r}")


def render(unit: dict, source: Path) -> str:
    unknown = set(unit) - set(FIELD_ORDER)
    if unknown:
        raise ValueError(f"{source.name}: 未知字段 {sorted(unknown)}，请同步 FIELD_ORDER")

    parts = [HEADER]
    for field in FIELD_ORDER:
        if field in unit:
            parts.append(f"{field} = {fmt_scalar(unit[field])}\n")
    return "".join(parts)


def main() -> int:
    check_only = "--check" in sys.argv

    if not SRC_DIR.is_dir():
        sys.exit(f"源目录不存在: {SRC_DIR}")

    sources = sorted(SRC_DIR.glob("*.yaml"))
    if not sources:
        sys.exit(f"没有找到 YAML: {SRC_DIR}")

    rendered: dict[str, str] = {}
    seen: dict[str, Path] = {}

    for src in sources:
        with src.open(encoding="utf-8") as fh:
            unit = yaml.safe_load(fh) or {}
        if not isinstance(unit, dict):
            raise ValueError(f"{src.name}: 顶层必须是映射")

        unit.setdefault("id", src.stem)
        uid = unit["id"]
        if uid in seen:
            raise ValueError(f"重复 id {uid!r}: {src.name} 与 {seen[uid].name}")
        seen[uid] = src

        rendered[f"{uid}.tres"] = render(unit, src)

    if check_only:
        drifted = [
            name
            for name, content in rendered.items()
            if not (OUT_DIR / name).exists()
            or (OUT_DIR / name).read_text(encoding="utf-8") != content
        ]
        if drifted:
            print("生成物与源不一致: " + ", ".join(sorted(drifted)))
            return 1
        print(f"OK: {len(rendered)} 个资源与源一致")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, content in sorted(rendered.items()):
        target = OUT_DIR / name
        if target.exists() and target.read_text(encoding="utf-8") == content:
            continue
        target.write_text(content, encoding="utf-8", newline="\n")
        print(f"写入 {target.relative_to(ROOT)}")

    print(f"完成: {len(rendered)} 个资源")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### 5.11 `tools/data/units/archer.yaml`

```yaml
id: archer
display_name: 弓箭手
max_hp: 24
attack: 7
defense: 1
move_points: 4
attack_range_min: 2
attack_range_max: 3
move_type: foot
sprite_path: res://assets/sprites/archer.png
portrait_path: res://assets/sprites/portraits/archer.png
```

### 5.12 `tools/build.py`

```python
#!/usr/bin/env python3
"""构建封装：校验 + 测试 + 导出。路径全部相对项目根。"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GODOT = shutil.which("godot") or "godot"

TARGETS = {
    "windows": ("Windows Desktop", "build/windows/tactics.exe"),
    "linux": ("Linux/X11", "build/linux/tactics.x86_64"),
}


def run(args: list[str]) -> None:
    print("+", " ".join(args), flush=True)
    proc = subprocess.run(args, cwd=ROOT)
    if proc.returncode != 0:
        raise SystemExit(f"命令失败，退出码 {proc.returncode}")


def check() -> None:
    run([sys.executable, str(ROOT / "tools" / "gen_units.py"), "--check"])


def test() -> None:
    gut = ROOT / "addons" / "gut" / "gut_cmdln.gd"
    if not gut.exists():
        print("跳过：未安装 GUT 插件")
        return
    run([
        GODOT, "--headless", "--path", str(ROOT),
        "-s", "addons/gut/gut_cmdln.gd",
        "-gdir=res://tests", "-gexit",
    ])


def export(target: str) -> None:
    if target not in TARGETS:
        raise SystemExit(f"未知目标 {target!r}，可选: {', '.join(TARGETS)}")
    preset, out = TARGETS[target]
    (ROOT / out).parent.mkdir(parents=True, exist_ok=True)
    run([GODOT, "--headless", "--path", str(ROOT),
         "--export-release", preset, out])


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        print("用法: python3 tools/build.py [check|test|export <windows|linux>|all]")
        return 2

    cmd, *rest = argv
    if cmd == "check":
        check()
    elif cmd == "test":
        test()
    elif cmd == "export":
        export(rest[0] if rest else "windows")
    elif cmd == "all":
        check()
        test()
        export("windows")
    else:
        raise SystemExit(f"未知命令 {cmd!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### 5.13 `README.md`

````markdown
# Tactics

像素 HD-2D 战棋。Ubuntu 侧做逻辑与构建，Windows 侧做场景与视觉。

## 快速开始

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r tools/requirements.txt

python3 tools/gen_units.py          # YAML -> data/units/*.tres
python3 tools/build.py check        # 校验生成物
python3 tools/build.py export windows
```

## 约束

- Godot 版本锁 **4.7.2**，两端一致
- `core/` 下不出现 `extends Node`
- `data/` 是生成物，改 `tools/data/` 后重新生成
- `scenes/` 由 Windows 侧独占编辑
- HD-2D 依赖 **Forward+** 渲染器，不要退回 `gl_compatibility`
````

### 5.14 `docs/workflow.md`

```markdown
# Windows ⇄ Ubuntu 分工

| 路径 | 归属 |
|---|---|
| `scenes/` | Windows 独占 |
| `assets/` 视觉 | Windows 独占 |
| `core/` | Ubuntu 独占 |
| `data/*.tres` | Ubuntu 生成 |
| `tools/` | Ubuntu |
| `tests/` | Ubuntu 主写 |
| `project.godot` / `export_presets.cfg` | 改前告知 |

开工：`git pull --rebase --autostash`
收工：`git push`

**永远不要两边同时编辑同一个 `.tscn`。**

`.tscn` 冲突处理：
```bash
git checkout --theirs scenes/battle.tscn
git add scenes/battle.tscn
```
然后回 Windows 编辑器重做本地改动。
```

### 5.15 初始化脚本

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$HOME/work/tactics}"
mkdir -p "$ROOT" && cd "$ROOT"

mkdir -p core data/units scenes/world scenes/ui tests docs tools/data/units
mkdir -p assets/sprites/portraits assets/tiles assets/audio
touch data/units/.gitkeep tests/.gitkeep
touch assets/sprites/.gitkeep assets/tiles/.gitkeep assets/audio/.gitkeep

# 逐一写入 5.2 – 5.14 的文件内容
# ...

git init -b main
git config core.autocrlf false
git config core.eol lf
git lfs install --local
git lfs track "*.png" "*.ogg" "*.wav" "*.mp3" "*.ttf" "*.otf" > /dev/null

python3 -m venv .venv
.venv/bin/pip install -q -r tools/requirements.txt

echo "✔ 脚手架完成: $ROOT"
```

> **顺序要求**：先写 `.gitattributes` 基础内容，再跑 `git lfs track`。反过来 LFS 规则可能覆盖文本规则。

---

## 6. 代码骨架（阶段 1 预留给 Ubuntu）

以下不要求现在创建，是阶段 1 的目标形态，供 agent 理解 `core/` 的写法约束：

```gdscript
# core/pathfinder.gd
class_name Pathfinder
extends RefCounted
## 移动范围计算。注意：用 Dijkstra，不是 BFS。
## BFS 只在「每格代价相同」时正确；地形消耗不同时必须用带优先队列的 Dijkstra。

const TERRAIN_COST := {
	&"grass": 1,
	&"forest": 2,
	&"mountain": 3,
	&"water": -1,   # 不可通行
}

static func reachable(grid: Array, start: Vector2i, move_points: int) -> Dictionary:
	## 返回 {Vector2i: 剩余移动力}
	pass
```

> 阶段 1 的任务就是把上面这个 `pass` 变成真实现，外加 `battle_state.gd`、`turn_manager.gd` 和对应 GUT 测试。

---

## 7. 验收检查

```bash
cd ~/work/tactics
source .venv/bin/activate

# 1. Godot 版本
godot --headless --version | grep -q "4.7.2" && echo "PASS 版本" || echo "FAIL 版本"

# 2. 项目 headless 加载无解析错误
godot --headless --path . --quit 2>&1 | grep -qi "error" && echo "FAIL 加载" || echo "PASS 加载"

# 3. 数据生成
python3 tools/gen_units.py
test -f data/units/archer.tres && echo "PASS 生成" || echo "FAIL 生成"

# 4. 幂等性
python3 tools/gen_units.py > /dev/null
git add -A
git status --porcelain data/ | grep -q . && echo "FAIL 非幂等" || echo "PASS 幂等"

# 5. --check 模式
python3 tools/build.py check && echo "PASS check" || echo "FAIL check"

# 6. 无 CRLF 混入
grep -rIl $'\r' --include="*.gd" --include="*.tscn" --include="*.tres" . \
  && echo "FAIL 有 CRLF" || echo "PASS 无 CRLF"

# 7. .uid 不在忽略规则内
git check-ignore -v --no-index core/unit_data.gd.uid \
  && echo "FAIL uid 被忽略" || echo "PASS uid 可提交"

# 8. 导出
python3 tools/build.py export windows
test -f build/windows/tactics.exe && echo "PASS 导出" || echo "FAIL 导出"
```

> 第 7 条用 `--no-index` 检查规则本身，因为首次 import 前 `.uid` 还不存在。

---

## 8. HD-2D 技术方案

### 8.1 为什么不是"整屏降采样"

最常见的误解：像素游戏 = 低分辨率渲染再放大。

HD-2D **不是**这样。它的构成是：

| 元素 | 分辨率 |
|---|---|
| 3D 场景（几何、光照、阴影、景深） | 原生 1280×720 或更高 |
| 像素角色贴图 | 低分辨率（32×32），`nearest` 采样 |
| 2D UI | 随窗口缩放 |

如果把整个画面降到 480×270，3D 的景深和光照会全部糊掉，HD-2D 的意义就消失了。

### 8.2 相机

```gdscript
camera.projection = Camera3D.PROJECTION_PERSPECTIVE
camera.fov = 28.0                      # 小 FOV ≈ 正交，压缩纵深
camera.rotation_degrees = Vector3(-30, 0, 0)
```

- **固定俯角**（28–35°）是风格来源，不做自由旋转
- 小 FOV 让远近物体大小差异小，接近正交，像素不产生透视畸变

### 8.3 角色：Sprite3D

```gdscript
sprite3d.billboard = BaseMaterial3D.BILLBOARD_FIXED_Y
sprite3d.texture_filter = BaseMaterial3D.TEXTURE_FILTER_NEAREST
sprite3d.pixel_size = 0.02
sprite3d.alpha_cut = SpriteBase3D.ALPHA_CUT_DISCARD      # 关键
sprite3d.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_DOUBLE_SIDED
```

`ALPHA_CUT_DISCARD` 必须开，否则透明边缘会投出方形阴影，一眼假。

### 8.4 景深与像素的冲突

屏幕空间 DOF 会把像素角色一起模糊。两种解法：

1. **焦点锁定角色深度**（简单，够用）——`dof_blur_far_*` 只模糊远处
2. **分层渲染**（精确）——角色单独 `SubViewport` 渲染，`Compositor` 里合成，不参与 DOF

先做方案 1，视觉不够再上方案 2。

### 8.5 光影

角色建议 `unshaded = false` 但压低 `specular`，让角色接受环境光与阴影，同时保留像素原色。全 unshaded 会像贴纸。

### 8.6 探索与战斗共用一张地图

**不要做两个独立场景。** 同一张 3D 地图，切换模式：

| 模式 | 相机 | 输入 | 角色行为 |
|---|---|---|---|
| 探索 | 低角度近景 | 方向键自由走 | `CharacterBody3D` 碰撞移动 |
| 战斗 | 拉高俯视 | 点格子 | 吸附格子，Dijkstra 移动 |

过渡做成「镜头拉升 + 角色归位」的 Tween，观感接近三角战略的切换。

好处：地形数据一份、无需维护两套地图、视觉统一。

### 8.7 兼容性回退

`forward_plus` 需要 Vulkan。老机器或集显可能失败，建议**发布时检测并提示**，或提供 `--rendering-method gl_compatibility` 启动参数作为降级（会失去景深，但能跑）。

---

## 9. 路线图

| 阶段 | 内容 | 验收 | 估时 |
|---|---|---|---|
| **0** | 脚手架 + 跨平台链路 | Ubuntu 导出 exe，Windows 能启动，看到 3D 方块 | 3–5 天 |
| **1** | `core/` 战棋逻辑（纯数据，零渲染） | GUT 全绿：Dijkstra、伤害、回合状态机 | 2–3 周 |
| **2** | 3D 地形 + 探索移动 | 小人在场景里走，有碰撞与高低差 | 2–3 周 |
| **3** | 战棋接入同一地图 | 镜头拉升、格子高亮、回合跑通 | 3–4 周 |
| **4** | HD-2D 视觉打磨 | 景深、阴影、光照、像素对齐达标 | 3–6 周 |
| **5** | 内容 + Steam | 一关完整可玩，商店页上线 | 6–10 周 |

**核心原则**：阶段 1 完全不碰渲染。战棋逻辑与 2D/3D 无关，先把玩法跑通——玩法是风险，视觉是成本。

### Steam 时间线

- Steam Direct：**$100 / 每款游戏**
- 首次付费后 **30 天**才能发售
- 商店页 Coming Soon **至少 2 周**
- 阶段 5 一开始就注册，不要等做完

---

## 10. 坑清单

| 现象 | 原因 | 处理 |
|---|---|---|
| 画面糊、像素发虚 | 用了 `viewport` stretch | 改 `canvas_items`；确认 `default_texture_filter=0` |
| 没有景深/体积雾 | 渲染器是 `gl_compatibility` | 改 `forward_plus` |
| 角色阴影是方块 | `alpha_cut` 未开 | 设 `ALPHA_CUT_DISCARD` |
| 角色被 DOF 糊掉 | 焦点不在角色深度 | 锁焦点或分层渲染 |
| 导出报模板缺失 | 模板版本不符 | 目录必须是 `4.7.2.stable` |
| 资源加载失败 | `.uid` 被忽略 | 检查 `.gitignore` 无 `*.uid` |
| pull 后全是改动 | CRLF 混入 | `git add --renormalize .` |
| 生成物 diff 噪音 | 脚本非幂等 | 固定顺序/格式/不写时间戳 |
| 编辑器卡、import 失效 | 项目在网盘或网络挂载 | 必须本地磁盘 |
| UE 式包体焦虑 | 不必 | Godot HD-2D 包体约 50–120 MB |
| 老机器 Vulkan 失败 | `forward_plus` 要求 | 提供 `gl_compatibility` 启动降级 |

---

## 11. 参考作品

- **《三角战略》** —— HD-2D + 战棋的最直接参照
- **《八方旅人》** —— HD-2D 视觉定义者
- **《Into the Breach》** —— 信息完全公开的回合制设计
- **《火焰纹章》** —— 战场节奏与成长系统
- **《Wargroove》** —— 像素战棋的完成度基准

---

*文档版本：2026-11-12 · 适用 Godot 4.7.2 stable · 取代旧三份文档*
