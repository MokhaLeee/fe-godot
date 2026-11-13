# Tactics

像素 HD-2D 战棋。Ubuntu 侧做逻辑与构建，Windows 侧做场景与视觉。

内容来源：`~/fe6-rebuild`（FE6 反编译重建工程），移植路线见
[docs/port-fe6.md](docs/port-fe6.md)。

## 快速开始

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r tools/requirements.txt

python3 tools/gen_units.py          # YAML -> data/units/*.tres
python3 tools/gen_rng_golden.py     # RNG 黄金向量
python3 tools/extract_chapter.py --chapter 1   # fe6-rebuild -> data/fe6/ch01 + assets/tiles/
python3 tools/build.py check        # 校验所有生成物
python3 tools/build.py test         # headless 跑 tests/*.gd
python3 tools/build.py export windows
```

Godot 二进制不在 PATH 时，`tools/build.py` 会回退到 `~/tools/Godot_v4.7.2-stable_linux.*`；
也可以显式建软链：

```bash
sudo ln -sf ~/tools/Godot_v4.7.2-stable_linux.x86_64 /usr/local/bin/godot
```

## 约束

- Godot 版本锁 **4.7.2**，两端一致
- `core/` 下不出现 `extends Node`
- `data/` 是生成物，改 `tools/data/` 或重跑导出后重新生成
- `scenes/` 由 Windows 侧独占编辑
- HD-2D 依赖 **Forward+** 渲染器，不要退回 `gl_compatibility`
- 内容导出只读 `~/fe6-rebuild`，不改它；路径可用 `FE6_ROOT` 覆盖
