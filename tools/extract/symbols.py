"""把 fe6-rebuild 的 include/ 枚举与 #define 收成一张 名字 → 整数 表。"""

from __future__ import annotations

from pathlib import Path

from . import cexpr

# 顺序有意义：后者可以覆盖前者（同名不同值以更具体的头文件为准）
_ENUM_HEADERS = [
    "include/constants/terrains.h",
    "include/constants/pids.h",
    "include/constants/jids.h",
    "include/constants/iids.h",
    "include/constants/songs.h",
    "include/constants/chapters.h",
    "include/constants/flags.h",
    "include/constants/faces.h",
    "include/constants/banims.h",
    "include/constants/skills.h",
    "include/constants/icons.h",
    "include/faction.h",
    "include/ai.h",
]

_DEFINE_HEADERS = [
    "include/constants/msg.h",
]


class Symbols:
    """名字 ↔ 整数 双向查询。

    导出 JSON 时同时保留符号名和数值：符号名字段给人看，数值字段给程序用。
    """

    def __init__(self, values: dict[str, int]):
        self.values = values
        self.by_value: dict[int, list[str]] = {}
        for name, value in values.items():
            self.by_value.setdefault(value, []).append(name)

    def __getitem__(self, name: str) -> int | None:
        return self.values.get(name)

    def name_of(self, value: int | None, prefix: str = "") -> str | None:
        """取数值对应的第一个符号名；`prefix` 用于消歧（如 "PID_"、"IID_"）。"""
        if value is None:
            return None
        candidates = self.by_value.get(value, [])
        if prefix:
            for name in candidates:
                if name.startswith(prefix):
                    return name
        return candidates[0] if candidates else None

    def resolve(self, token: str) -> tuple[str, int | None]:
        """把 `PID_ROY` / `0x0A` / `0` 统一成 (符号名或原文, 数值)。"""
        t = token.strip()
        literal = cexpr.parse_int(t)
        if literal is not None:
            return (self.name_of(literal) or str(literal)), literal
        return t, self.values.get(t)


def load(fe6_root: Path) -> Symbols:
    values: dict[str, int] = {}
    for rel in _ENUM_HEADERS:
        path = fe6_root / rel
        if path.is_file():
            values = cexpr.parse_enum_blocks(cexpr.read(path), values)
    for rel in _DEFINE_HEADERS:
        path = fe6_root / rel
        if path.is_file():
            values = cexpr.parse_defines(cexpr.read(path), values)
    return Symbols(values)
