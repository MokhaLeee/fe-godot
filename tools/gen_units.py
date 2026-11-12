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
