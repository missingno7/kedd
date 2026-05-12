from __future__ import annotations

from dataclasses import dataclass
from math import ceil, sqrt
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from PIL import Image, ImageDraw

from kegg.formats.bob import parse_bob_header
from kegg.formats.cod import decode_file
from kegg.formats.bob_decode import decode_bob_sprites
from kegg.formats.palette import RGB, default_palette, load_vga_palette


@dataclass(frozen=True)
class BobPreviewInfo:
    file_name: str
    object_count: int
    width: int
    height: int
    header_size: int
    payload_size: int
    note: str


def _palette_for(data_dir: Path) -> List[RGB]:
    pal = data_dir / "KE_ALL.PAL"
    if pal.exists():
        try:
            return load_vga_palette(pal)
        except Exception:
            pass
    return default_palette()


def bob_preview_info(path: Path) -> BobPreviewInfo:
    header = parse_bob_header(path)
    data = decode_file(path).data
    return BobPreviewInfo(
        file_name=path.name,
        object_count=header.object_count,
        width=header.width,
        height=header.height,
        header_size=header.header_size,
        payload_size=max(0, len(data) - header.header_size),
        note="Raw debug preview only: BOB blitter/RLE is not fully decoded yet.",
    )


def make_raw_bob_atlas(path: Path, data_dir: Path, max_columns: int = 16, scale: int = 3) -> Image.Image:
    """Create the best-current BOB atlas preview.

    This now uses the solved-enough x%4 plane decoder. The mask/blitter metadata
    chunk is still not interpreted, but the visible brick sprites are recognizable.
    """
    sprites, metas = decode_bob_sprites(path, data_dir)
    if not sprites:
        header = parse_bob_header(path)
        return Image.new("RGB", (max(1, header.width), max(1, header.height)), (20, 20, 20))

    count = min(len(sprites), 512)
    cols = max(1, min(max_columns, ceil(sqrt(count))))
    rows = ceil(count / cols)
    gap = 3
    label_h = 10
    w = max(sprite.width for sprite in sprites[:count])
    h = max(sprite.height for sprite in sprites[:count])
    cell_w = w + gap * 2
    cell_h = h + gap * 2 + label_h
    image = Image.new("RGB", (cols * cell_w, rows * cell_h), (20, 20, 20))
    draw = ImageDraw.Draw(image)

    for idx, sprite in enumerate(sprites[:count]):
        x0 = (idx % cols) * cell_w + gap
        y0 = (idx // cols) * cell_h + gap
        image.paste(sprite.convert("RGB"), (x0, y0))
        draw.rectangle((x0 - 1, y0 - 1, x0 + sprite.width, y0 + sprite.height), outline=(60, 60, 60))
        draw.text((x0, y0 + h + 1), str(idx), fill=(180, 180, 180))

    if scale != 1:
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    return image


def save_raw_bob_atlas(path: Path, data_dir: Path, out_dir: Path, scale: int = 3) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    image = make_raw_bob_atlas(path, data_dir=data_dir, scale=scale)
    out_path = out_dir / f"{path.stem}.raw_bob_atlas.png"
    image.save(out_path)
    return out_path
