"""tileset 目录 → Godot 图集 + metatile 表。

`ConfImg.png` 是 512×512 的 8bpp 源图，正好是 32×32 = 1024 个 16×16 metatile
按行排布。它已经逐像素验证过与「TSA + Img1 + Img2 展开结果」一致
（见 fe6-rebuild `docs/map-rendering.md`），所以可以直接当 Godot 的
TileSet 图集用：atlas 坐标 = (metatile_id % 32, metatile_id // 32)。

本模块只负责「算」：返回 JSON 文本与 PNG 字节，写盘交给调用方。
"""

from __future__ import annotations

import json
from pathlib import Path

from . import mapdata
from .symbols import Symbols

ATLAS_COLS = 32
METATILE_PX = 16


def build(tileset_dir: Path, symbols: Symbols, res_dir: str) -> tuple[dict, str, bytes, str]:
    """返回 (payload, JSON 文本, atlas PNG 字节, TileSet .tres 文本)。

    `res_dir` 是该 tileset 在项目里的目录（如 `assets/tiles/mapasset01`），
    用来拼 `.tres` 里的 `res://` 引用。
    """
    refs, terrain_lut = mapdata.read_tsaconf(tileset_dir / "TsaConf.dmp")
    metatiles = [
        {
            "id": i,
            "terrain": lut,
            "terrain_name": symbols.name_of(lut, "TERRAIN_"),
            "tiles": list(refs[i]),
        }
        for i, lut in enumerate(terrain_lut)
    ]

    payload = {
        "name": tileset_dir.name,
        "atlas": "atlas.png",
        "metatile_px": METATILE_PX,
        "atlas_cols": ATLAS_COLS,
        "count": len(metatiles),
        "metatiles": metatiles,
    }
    json_text = json.dumps(payload, ensure_ascii=False, indent=1) + "\n"
    atlas = (tileset_dir / "ConfImg.png").read_bytes()
    return payload, json_text, atlas, build_tres(res_dir)


def build_tres(res_dir: str) -> str:
    """生成 Godot TileSet 资源：1024 个 16×16 tile，atlas 坐标 = (id % 32, id // 32)。

    这样场景侧直接 `TileMapLayer.tile_set = load(...)` 就能用 metatile id 落格，
    不需要在编辑器里手点 1024 个图块。
    """
    lines = [
        '[gd_resource type="TileSet" load_steps=3 format=3]',
        "",
        f'[ext_resource type="Texture2D" path="res://{res_dir}/atlas.png" id="1_atlas"]',
        "",
        '[sub_resource type="TileSetAtlasSource" id="TileSetAtlasSource_1"]',
        'texture = ExtResource("1_atlas")',
        f"texture_region_size = Vector2i({METATILE_PX}, {METATILE_PX})",
    ]
    for y in range(ATLAS_COLS):
        for x in range(ATLAS_COLS):
            lines.append(f"{x}:{y}/0 = 0")
    lines += [
        "",
        "[resource]",
        f"tile_size = Vector2i({METATILE_PX}, {METATILE_PX})",
        'sources/0 = SubResource("TileSetAtlasSource_1")',
        "",
    ]
    return "\n".join(lines)
