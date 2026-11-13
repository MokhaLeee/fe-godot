"""章节地图：`.dmp` 数据 + tileset 的 metatile 定义 → 网格 JSON + 预览 PNG。

数据布局（与 fe6-rebuild `tools/maptools/render_chapter.py` 一致）：

```
MapTsa_*.dmp        u8 width; u8 height; u16 cells[width*height]
                    每格 = metatile_id << 2（低 2 位恒为 0）
TsaConf.dmp         u16 tiles[1024][4]   // 左上、右上、左下、右下
                    后 1024 字节        // 每个 metatile 的 terrain id
```

地形 id 直接从 tileset 的 LUT 查，不依赖章节自己的地形表。

本模块只负责「算」：返回 JSON 文本与 PNG 字节，写盘交给调用方（便于 `--check`）。
"""

from __future__ import annotations

import io
import json
import struct
from pathlib import Path

from PIL import Image


def read_map(dmp_path: Path) -> tuple[int, int, list[int]]:
    """读章节地图，返回 (width, height, metatile_ids)。"""
    raw = dmp_path.read_bytes()
    if len(raw) < 2:
        raise ValueError(f"{dmp_path}: 文件过短")
    width, height = raw[0], raw[1]
    need = 2 + width * height * 2
    if len(raw) < need:
        raise ValueError(f"{dmp_path}: 期望 {need} 字节，实际 {len(raw)}")
    cells = struct.unpack("<%dH" % (width * height), raw[2:need])
    metatiles = [c >> 2 for c in cells]
    return width, height, metatiles


def read_tsaconf(dmp_path: Path) -> tuple[list[tuple[int, int, int, int]], list[int]]:
    """读 tileset 的 TsaConf，返回 (1024 个 metatile 的 4 个 tile 引用, 1024 个地形 id)。"""
    raw = dmp_path.read_bytes()
    if len(raw) < 8192 + 1024:
        raise ValueError(f"{dmp_path}: 期望 9216 字节，实际 {len(raw)}")
    refs = struct.unpack("<4096H", raw[:8192])
    groups = [tuple(refs[i * 4 : i * 4 + 4]) for i in range(1024)]
    terrain = list(raw[8192 : 8192 + 1024])
    return groups, terrain


def terrain_grid(metatiles: list[int], terrain_lut: list[int]) -> list[int]:
    return [terrain_lut[m] for m in metatiles]


def render(
    metatiles: list[int],
    width: int,
    height: int,
    tileset_dir: Path,
    scale: int = 1,
) -> Image.Image:
    """按 TSA 展开成 RGB 图；与 ROM 内观感一致（不依赖 ROM）。"""
    refs, _ = read_tsaconf(tileset_dir / "TsaConf.dmp")
    conf = Image.open(tileset_dir / "ConfImg.png").convert("P")
    palette = conf.getpalette()[: 256 * 3]
    img1 = Image.open(tileset_dir / "Img1.png").convert("P")
    img2 = Image.open(tileset_dir / "Img2.png").convert("P")
    p1, p2 = img1.load(), img2.load()

    canvas = Image.new("P", (width * 16, height * 16), 0)
    canvas.putpalette(palette)
    px = canvas.load()

    for y in range(height):
        for x in range(width):
            m = metatiles[y * width + x]
            if m >= len(refs):
                continue
            for lane, ref in enumerate(refs[m]):
                tile = ref & 0x3FF
                palid = (ref >> 12) & 0xF
                hflip = bool(ref & 0x400)
                vflip = bool(ref & 0x800)
                src = p1 if tile < 512 else p2
                t = tile if tile < 512 else tile - 512
                sx, sy = (t % 32) * 8, (t // 32) * 8
                ox = x * 16 + (lane % 2) * 8
                oy = y * 16 + (lane // 2) * 8
                for yy in range(8):
                    iy = 7 - yy if vflip else yy
                    for xx in range(8):
                        ix = 7 - xx if hflip else xx
                        px[ox + xx, oy + yy] = (palid << 4) | src[sx + ix, sy + iy]

    out = canvas.convert("RGB")
    if scale > 1:
        out = out.resize((out.width * scale, out.height * scale), Image.NEAREST)
    return out


def build(
    dmp_path: Path,
    tileset_dir: Path,
    terrain_names: dict[int, str],
    scale: int = 2,
) -> tuple[dict, str, bytes]:
    """返回 (payload, JSON 文本, PNG 字节)。"""
    width, height, metatiles = read_map(dmp_path)
    _, lut = read_tsaconf(tileset_dir / "TsaConf.dmp")
    terrain = terrain_grid(metatiles, lut)

    payload = {
        "source": dmp_path.name,
        "tileset": tileset_dir.name,
        "width": width,
        "height": height,
        "metatile": metatiles,
        "terrain": terrain,
        "terrain_names": {str(k): v for k, v in sorted(terrain_names.items())},
    }

    buf = io.BytesIO()
    render(metatiles, width, height, tileset_dir, scale=scale).save(buf, format="PNG")
    return payload, format_json(payload), buf.getvalue()


def format_json(payload: dict) -> str:
    """网格数组按行折叠，字段顺序固定，便于 review 与 diff。"""
    lines = ["{"]
    for key in ("source", "tileset", "width", "height"):
        lines.append(f'  "{key}": {json.dumps(payload[key], ensure_ascii=False)},')
    for key in ("metatile", "terrain"):
        lines.append(f'  "{key}": {json.dumps(payload[key])},')
    names = json.dumps(payload["terrain_names"], ensure_ascii=False, indent=1)
    names = "\n".join("  " + ln for ln in names.splitlines()).strip()
    lines.append('  "terrain_names": ' + names)
    lines.append("}")
    return "\n".join(lines) + "\n"
