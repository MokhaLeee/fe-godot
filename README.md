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
