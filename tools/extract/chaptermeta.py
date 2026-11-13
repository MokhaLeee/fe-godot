"""`ChapterInfoTable` → 章节元数据（相机初始位置、tileset、BGM、胜利条件文本 id…）。

只取做内容管线需要的字段；数组字段（tactics_ranks 之类）跳过。
"""

from __future__ import annotations

import re
from pathlib import Path

from . import cexpr
from .symbols import Symbols

_DECL = re.compile(r"struct\s+ChapterInfo\s+(?:const\s+|CONST_DATA\s+)*([A-Za-z_]\w*)\s*\[\s*\]\s*=")
_ENTRY = re.compile(r"\[\s*([A-Za-z_]\w*)\s*\]\s*=")

_WANTED = (
    "debug_name",
    "asset_img_a",
    "asset_img_b",
    "asset_pal",
    "asset_tileset",
    "asset_map",
    "asset_map_changes",
    "asset_event_info",
    "has_prep",
    "title_id",
    "coord_x",
    "coord_y",
    "song_blue_bgm",
    "song_red_bgm",
    "song_green_bgm",
    "song_intro_bgm",
    "song_opening_bgm",
    "msg_clear_condition",
    "msg_upper_army",
    "msg_lower_army",
    "msg_chapter_title",
)


def _value(token: str, symbols: Symbols):
    """字段值原样保留符号名（`PLIST_CH1_MAP`、`SONG_0A`），数字转 int。

    这里**不**做「数字 → 名字」反查：章节表里的 9 可能是坐标，也可能是别的
    命名空间里的常量，猜出来的名字只会误导。消费端用 symbols.json 反查。
    """
    t = token.strip()
    if not t:
        return None
    if t.startswith("{"):
        return None
    if t in ("true", "false"):
        return t == "true"
    if t.startswith('"') and t.endswith('"'):
        return t[1:-1]
    literal = cexpr.parse_int(t)
    if literal is not None:
        return literal
    return t


def parse(path: Path, symbols: Symbols) -> dict[str, dict]:
    """返回 {CHAPTER_常量名: 字段字典}。"""
    text = cexpr.read(path)
    out: dict[str, dict] = {}

    for table, body, _line in cexpr.find_initializers(text, _DECL.pattern):
        if table != "ChapterInfoTable":
            continue
        for m in _ENTRY.finditer(body):
            open_idx = body.find("{", m.end())
            if open_idx < 0:
                continue
            close_idx = cexpr.match_brace(body, open_idx)
            if close_idx < 0:
                continue
            fields: dict = {}
            for item in cexpr.split_top(body[open_idx + 1 : close_idx]):
                key, sep, value = item.partition("=")
                if not sep:
                    continue
                key = key.strip().lstrip(".")
                if key not in _WANTED:
                    continue
                parsed = _value(value, symbols)
                if parsed is not None:
                    fields[key] = parsed
            out[m.group(1)] = fields
    return out
