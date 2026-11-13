"""`texts/**/*.txt` → 对白 JSON。

文本文件是「`## MSG_xxx` + 正文」的块结构，正文里带原版控制码
（`[LoadFace]`、`[TAB]`、`[A]`、`[X]` 等）。控制码**保留原样**，
由表现层解析；导出只做结构化和 ID 解析。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .symbols import Symbols

_BLOCK = re.compile(r"^##\s+([A-Za-z0-9_]+)\s*$", re.M)


def parse_file(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    matches = list(_BLOCK.finditer(text))
    entries: list[dict] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end() : end].strip("\n")
        if body.strip():
            entries.append({"id": m.group(1), "text": body})
    return entries


def export(path: Path, symbols: Symbols) -> dict:
    entries = parse_file(path)
    for entry in entries:
        entry["msg_id"] = symbols[entry["id"]]
    return {
        "source": str(path),
        "count": len(entries),
        "entries": entries,
    }
