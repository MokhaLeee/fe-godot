#!/usr/bin/env python3
"""把 fe6-rebuild 的一章导出成 Godot 可直接消费的 JSON/PNG。

用法：

```bash
python3 tools/extract_chapter.py --chapter 1
python3 tools/extract_chapter.py --chapter 1 --check   # 只校验是否最新
FE6_ROOT=/path/to/fe6-rebuild python3 tools/extract_chapter.py
```

产出：

```
data/fe6/ch01/chapter.json     章节元数据（相机起点、tileset、BGM、条件文本）
data/fe6/ch01/map.json         width/height + metatile[] + terrain[]
data/fe6/ch01/units.json       UnitInfo 表 + ChapterEventInfo 的挂接关系
data/fe6/ch01/events.json      EventScr / EventListScr / MoveScr 指令流
data/fe6/ch01/texts.json       本章对白（带原版控制码）
data/fe6/symbols.json          名字 ↔ 整数（PID/IID/MSG/TERRAIN/…）
assets/tiles/mapasset01/atlas.png        metatile 图集（16×16，32 列）
assets/tiles/mapasset01/metatiles.json
data/fe6/ch01/preview.png     2 倍地图预览
```

幂等：输出只含从源码确定的内容，不含时间戳；内容相同则不写盘。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from extract import (  # noqa: E402
    chaptermeta,
    cexpr,
    events,
    mapdata,
    symbols as symmod,
    texts,
    tileset,
    units,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FE6 = Path(os.environ.get("FE6_ROOT", Path.home() / "fe6-rebuild"))

# CHAPTER_* → 源码文件名主干（对应 gameinfo/chapterinfo/events/<stem>.c）
CHAPTER_STEMS = {
    "CHAPTER_TUTORIAL": "ch0",
    "CHAPTER_1": "ch1",
    "CHAPTER_2": "ch2",
    "CHAPTER_3": "ch3",
    "CHAPTER_4": "ch4",
    "CHAPTER_5": "ch5",
    "CHAPTER_6": "ch6",
    "CHAPTER_7": "ch7",
    "CHAPTER_8": "ch8",
    "CHAPTER_9": "ch9",
    "CHAPTER_10_A": "ch10a",
    "CHAPTER_10_B": "ch10b",
    "CHAPTER_11_A": "ch11a",
    "CHAPTER_11_B": "ch11b",
    "CHAPTER_12": "ch12",
    "CHAPTER_13": "ch13",
    "CHAPTER_14": "ch14",
    "CHAPTER_15": "ch15",
    "CHAPTER_16": "ch16",
    "CHAPTER_17_I": "ch17a",
    "CHAPTER_17_S": "ch17b",
    "CHAPTER_18_I": "ch18a",
    "CHAPTER_18_S": "ch18b",
    "CHAPTER_19_I": "ch19a",
    "CHAPTER_19_S": "ch19b",
    "CHAPTER_20_I": "ch20a",
    "CHAPTER_20_S": "ch20b",
    "CHAPTER_21": "ch21",
    "CHAPTER_22": "ch22",
    "CHAPTER_23": "ch23",
    "CHAPTER_24": "ch24",
    "CHAPTER_FINAL": "final",
    "CHAPTER_8X": "ch8x",
    "CHAPTER_12X": "ch12x",
    "CHAPTER_14X": "ch14x",
    "CHAPTER_16X": "ch16x",
    "CHAPTER_20X_I": "ch20ax",
    "CHAPTER_20X_S": "ch20bx",
    "CHAPTER_21X": "ch21x",
    "CHAPTER_TRIAL_A": "trail1",
    "CHAPTER_TRIAL_B": "trail2",
    "CHAPTER_TRIAL_C": "trail3",
    "CHAPTER_TRIAL_D": "trail4",
    "CHAPTER_TRIAL_E": "trail5",
}

# 章节号 → (contents/maps 下的目录名, 地图文件名主干)
# 目前只有第 1 章有可编辑的地图源；其余章节的地图仍在 ROM 里，等 M1 之后补。
MAP_SOURCES = {"CHAPTER_1": ("Chapter01", "MapTsa_Ch1")}
TILESETS = {"CHAPTER_1": "MapAsset01"}


def chapter_symbol(number: int) -> str:
    return "CHAPTER_TUTORIAL" if number == 0 else f"CHAPTER_{number}"


class Writer:
    """统一写盘：内容相同跳过；--check 只报告差异。"""

    def __init__(self, check_only: bool):
        self.check_only = check_only
        self.drift: list[Path] = []

    def json(self, path: Path, payload) -> None:
        self.text(path, json.dumps(payload, ensure_ascii=False, indent=1) + "\n")

    def text(self, path: Path, content: str) -> None:
        self._commit(path, content.encode("utf-8"))

    def binary(self, path: Path, blob: bytes) -> None:
        self._commit(path, blob)

    def _commit(self, path: Path, blob: bytes) -> None:
        if path.is_file() and path.read_bytes() == blob:
            return
        if self.check_only:
            self.drift.append(path)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        print(f"写入 {path.relative_to(ROOT)}")


def export_chapter(fe6: Path, number: int, out: Writer) -> int:
    symbol = chapter_symbol(number)
    stem = CHAPTER_STEMS.get(symbol)
    if stem is None:
        print(f"未知章节 {symbol}", file=sys.stderr)
        return 2

    sym = symmod.load(fe6)
    out_dir = ROOT / "data" / "fe6" / f"ch{number:02d}"

    # ── 章节元数据 ────────────────────────────────────────────
    metas = chaptermeta.parse(fe6 / "gameinfo/chapterinfo/chapterinfo_data.c", sym)
    meta = metas.get(symbol)
    if meta is None:
        print(f"{symbol} 不在 ChapterInfoTable 里", file=sys.stderr)
        return 2

    # ── 地图 ──────────────────────────────────────────────────
    counts: dict[str, int] = {}
    map_info = None
    if symbol in MAP_SOURCES:
        map_dir, map_stem = MAP_SOURCES[symbol]
        map_base = fe6 / "contents" / "maps" / map_dir
        tileset_dir = fe6 / "contents" / "tileset" / TILESETS[symbol]
        tileset_out = ROOT / "assets" / "tiles" / TILESETS[symbol].lower()
        res_dir = f"assets/tiles/{TILESETS[symbol].lower()}"

        ts_payload, ts_json, atlas_png, ts_tres = tileset.build(tileset_dir, sym, res_dir)
        out.text(tileset_out / "metatiles.json", ts_json)
        out.binary(tileset_out / "atlas.png", atlas_png)
        out.text(tileset_out / "tileset.tres", ts_tres)

        # 同一 terrain id 可能有多个别名（TERRAIN_GATE_0B / TERRAIN_GATE_23 等），
        # 按字母序取第一个，保证输出确定。
        terrain_names: dict[int, str] = {}
        for name in sorted(n for n in sym.values if n.startswith("TERRAIN_")):
            terrain_names.setdefault(sym.values[name], name)

        payload, json_text, preview_png = mapdata.build(
            map_base / f"{map_stem}.dmp", tileset_dir, terrain_names
        )
        out.text(out_dir / "map.json", json_text)
        out.binary(out_dir / "preview.png", preview_png)
        map_info = {"width": payload["width"], "height": payload["height"]}
        counts["metatiles"] = ts_payload["count"]

    # ── 单位 / 事件 ───────────────────────────────────────────
    events_path = fe6 / "gameinfo" / "chapterinfo" / "events" / f"{stem}.c"
    unit_tables = units.parse(events_path, sym) if events_path.is_file() else {}
    event_data = (
        events.parse(events_path)
        if events_path.is_file()
        else {"event_scripts": {}, "event_lists": {}, "move_scripts": {}}
    )
    wiring = chapter_wiring(events_path) if events_path.is_file() else {}

    # ── 文本 ──────────────────────────────────────────────────
    text_path = fe6 / "texts" / "events" / f"{stem}.txt"
    text_data = texts.export(text_path, sym) if text_path.is_file() else {"count": 0, "entries": []}

    # ── 落盘 ──────────────────────────────────────────────────
    counts.update(
        {
            "unit_tables": len(unit_tables),
            "event_scripts": len(event_data["event_scripts"]),
            "event_lists": len(event_data["event_lists"]),
            "move_scripts": len(event_data["move_scripts"]),
            "texts": text_data["count"],
        }
    )
    out.json(
        out_dir / "chapter.json",
        {
            "symbol": symbol,
            "index": sym[symbol],
            "stem": stem,
            "meta": meta,
            "map": map_info,
            "counts": counts,
        },
    )
    out.json(out_dir / "units.json", {"tables": unit_tables, "wiring": wiring})
    out.json(out_dir / "events.json", event_data)
    out.json(out_dir / "texts.json", text_data)
    out.json(ROOT / "data" / "fe6" / "symbols.json", export_symbols(sym))

    if not out.check_only:
        print(
            f"完成 {symbol}: 地图 {map_info}, {counts['unit_tables']} 个单位表, "
            f"{counts['event_scripts']} 个事件脚本, {counts['texts']} 条文本"
        )
    return 0


_SYMBOL_PREFIXES = {
    "TERRAIN",
    "PID",
    "JID",
    "IID",
    "SONG",
    "CHAPTER",
    "FACTION",
    "AI",
    "FLAG",
    "TILE",
    "MSG",
    "BACKGROUND",
    "ITEM",
    "EVENT",
}


def export_symbols(sym: symmod.Symbols) -> dict:
    return {
        name: value
        for name, value in sorted(sym.values.items())
        if name.split("_")[0] in _SYMBOL_PREFIXES
    }


def chapter_wiring(events_path: Path) -> dict:
    """读 `struct ChapterEventInfo const ChapterEventInfo_X = {...}` 的字段指向。"""
    text = cexpr.read(events_path)
    import re

    m = re.search(r"struct\s+ChapterEventInfo\s+(?:const\s+)?([A-Za-z_]\w*)\s*=", text)
    if not m:
        return {}
    open_idx = text.find("{", m.end())
    if open_idx < 0:
        return {}
    close_idx = cexpr.match_brace(text, open_idx)
    if close_idx < 0:
        return {}
    wiring: dict = {}
    for item in cexpr.split_top(text[open_idx + 1 : close_idx]):
        key, sep, value = item.partition("=")
        if sep:
            wiring[key.strip().lstrip(".")] = value.strip()
    return wiring


def main() -> int:
    ap = argparse.ArgumentParser(description="导出一章的地图/单位/事件/文本")
    ap.add_argument("--chapter", type=int, default=1, help="章节号（0 = 教学）")
    ap.add_argument("--fe6", type=Path, default=DEFAULT_FE6, help="fe6-rebuild 根目录")
    ap.add_argument("--check", action="store_true", help="只校验生成物是否最新")
    args = ap.parse_args()

    if not (args.fe6 / "Makefile").is_file():
        print(f"{args.fe6} 不像 fe6-rebuild 根目录（缺 Makefile）", file=sys.stderr)
        return 2

    out = Writer(args.check)
    code = export_chapter(args.fe6, args.chapter, out)
    if out.check_only and out.drift:
        for path in out.drift:
            print(f"drift: {path.relative_to(ROOT)}", file=sys.stderr)
        return 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
