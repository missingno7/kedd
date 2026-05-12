from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Iterable, List, Tuple

from PIL import Image, ImageDraw, ImageOps

from kegg.formats.bob import parse_bob_header
from kegg.formats.cod import decode_file
from kegg.graphics.bob_preview import make_raw_bob_atlas


def classify_asset(path: Path) -> str:
    stem = path.stem.upper()
    if stem == 'KE_BRICK':
        return 'Bricks / level blocks'
    if stem == 'KE_FILL':
        return 'Background / fill tiles / frame pieces'
    if stem == 'KE_RACK':
        return 'Paddles (rackets) and paddle-like bars'
    if stem == 'KE_NMY':
        return 'Enemies / flying creatures / hazards'
    if stem == 'KE_MONST':
        return 'Monster / enemy fragments or alternate enemy set'
    if stem == 'KE_SPELL':
        return 'Powerups / projectiles / balls / special items'
    if stem == 'KE_DIGIT':
        return 'Score digits'
    if stem == 'KE_FONT':
        return 'Font / UI letters'
    if stem == 'KE_MENU':
        return 'Menu widgets / small UI pieces'
    if path.suffix.upper() == '.GIF':
        return 'Full-screen decoded image'
    return 'Unknown / miscellaneous'


def _title_card(title: str, subtitle: str, body: Image.Image) -> Image.Image:
    margin = 8
    header_h = 34
    footer_h = 18 if subtitle else 0
    canvas = Image.new('RGB', (body.width + margin * 2, body.height + header_h + footer_h + margin * 2), (18, 18, 22))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, canvas.width - 1, canvas.height - 1), outline=(70, 70, 80))
    draw.rectangle((0, 0, canvas.width - 1, header_h + margin - 1), fill=(28, 28, 36))
    draw.text((margin, 8), title, fill=(235, 235, 235))
    if subtitle:
        draw.text((margin, header_h + body.height + margin), subtitle, fill=(160, 190, 160))
    canvas.paste(body, (margin, header_h))
    return canvas


def decode_gif_image(path: Path) -> Image.Image:
    data = decode_file(path).data
    return Image.open(BytesIO(data)).convert('RGBA')


def make_gif_preview(path: Path, scale: int = 1, max_width: int = 640) -> Image.Image:
    image = decode_gif_image(path)
    if scale != 1:
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    if image.width > max_width:
        ratio = max_width / image.width
        image = image.resize((int(image.width * ratio), int(image.height * ratio)), Image.Resampling.NEAREST)
    return image.convert('RGB')


def export_graphics_assets(data_dir: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    bob_out = out_dir / 'bob_previews'
    gif_out = out_dir / 'gif_previews'
    bob_out.mkdir(parents=True, exist_ok=True)
    gif_out.mkdir(parents=True, exist_ok=True)

    manifest: dict = {'bob_files': [], 'gif_files': []}

    for path in sorted(data_dir.glob('*.BOB')):
        atlas = make_raw_bob_atlas(path, data_dir=data_dir, scale=2)
        out_path = bob_out / f'{path.stem}.raw_bob_atlas.png'
        atlas.save(out_path)
        header = parse_bob_header(path)
        manifest['bob_files'].append({
            'file': path.name,
            'category': classify_asset(path),
            'count': header.object_count,
            'logical_size': [header.width, header.height],
            'atlas_png': str(out_path.relative_to(out_dir)),
        })

    for path in sorted(data_dir.glob('*.GIF')):
        preview = make_gif_preview(path, scale=1, max_width=480)
        out_path = gif_out / f'{path.stem}.png'
        preview.save(out_path)
        manifest['gif_files'].append({
            'file': path.name,
            'category': classify_asset(path),
            'size': list(preview.size),
            'png': str(out_path.relative_to(out_dir)),
        })

    (out_dir / 'graphics_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def _make_overview_tiles(data_dir: Path, export_dir: Path) -> List[Image.Image]:
    tiles: List[Image.Image] = []
    for path in sorted(data_dir.glob('*.BOB')):
        atlas_path = export_dir / 'bob_previews' / f'{path.stem}.raw_bob_atlas.png'
        atlas = Image.open(atlas_path).convert('RGB')
        # keep large atlases readable but not enormous
        max_width = 760
        if atlas.width > max_width:
            ratio = max_width / atlas.width
            atlas = atlas.resize((int(atlas.width * ratio), int(atlas.height * ratio)), Image.Resampling.NEAREST)
        header = parse_bob_header(path)
        subtitle = f"{classify_asset(path)} | count={header.object_count} | logical={header.width}x{header.height}"
        tiles.append(_title_card(path.name, subtitle, atlas))
    for path in sorted(data_dir.glob('*.GIF')):
        image = make_gif_preview(path, scale=1, max_width=760)
        subtitle = f"{classify_asset(path)} | {image.width}x{image.height}"
        tiles.append(_title_card(path.name, subtitle, image))
    return tiles


def build_graphics_overview(data_dir: Path, out_dir: Path) -> Path:
    manifest = export_graphics_assets(data_dir, out_dir)
    tiles = _make_overview_tiles(data_dir, out_dir)
    if not tiles:
        image = Image.new('RGB', (640, 120), (15, 15, 18))
        ImageDraw.Draw(image).text((20, 20), 'No graphics assets found.', fill=(255, 255, 255))
        out_path = out_dir / 'graphics_overview.png'
        image.save(out_path)
        return out_path

    cols = 2
    gap = 12
    tile_w = max(tile.width for tile in tiles)
    row_heights: List[int] = []
    for row_start in range(0, len(tiles), cols):
        row_heights.append(max(tile.height for tile in tiles[row_start:row_start + cols]))
    width = cols * tile_w + gap * (cols + 1)
    height = sum(row_heights) + gap * (len(row_heights) + 1) + 50
    canvas = Image.new('RGB', (width, height), (10, 10, 14))
    draw = ImageDraw.Draw(canvas)
    draw.text((gap, 12), 'Krypton Egg graphics overview', fill=(255, 255, 255))
    draw.text((gap, 28), 'BOB atlases + decoded GIF screens (best-current decoding)', fill=(180, 180, 200))

    y = 50
    for row_idx, row_start in enumerate(range(0, len(tiles), cols)):
        x = gap
        row_h = row_heights[row_idx]
        for tile in tiles[row_start:row_start + cols]:
            canvas.paste(tile, (x, y))
            x += tile_w + gap
        y += row_h + gap

    out_path = out_dir / 'graphics_overview.png'
    canvas.save(out_path)
    return out_path
