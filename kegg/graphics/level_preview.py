from __future__ import annotations

from pathlib import Path
from typing import List

from PIL import Image, ImageDraw

from kegg.formats.bob_decode import decode_bob_sprites
from kegg.formats.level import (
    BRICK_GRID_HEIGHT,
    BRICK_GRID_WIDTH,
    RenderLevel,
    load_level_set,
    parse_render_levels,
)
from kegg.formats.palette import RGB, default_palette, load_vga_palette


BRICK_STEP_W = 16  # KE_BRICK sprite width 15 + one pixel spacing
BRICK_STEP_H = 9   # KE_BRICK sprite height 8 + one pixel spacing

# KE.EXE background filler:
#   table DS:0x2E9C points to KE_FILL.BOB sprites 6..46
#   ds:0xDF38 starts at -1 and increments on each new level, wrapping at 0x29
BACKGROUND_FILL_FIRST = 6
BACKGROUND_FILL_COUNT = 41


def _palette_for(data_dir: Path) -> List[RGB]:
    pal = data_dir / "KE_ALL.PAL"
    if pal.exists():
        try:
            return load_vga_palette(pal)
        except Exception:
            pass
    return default_palette()


def background_fill_sprite_id_for_level(level_number: int) -> int:
    return BACKGROUND_FILL_FIRST + ((max(1, level_number) - 1) % BACKGROUND_FILL_COUNT)


def make_background_grid(
    data_dir: Path,
    level_number: int,
    width: int,
    height: int,
    fill_sprite_id: int | None = None,
) -> Image.Image:
    fill_sprites, _ = decode_bob_sprites(data_dir / "KE_FILL.BOB", data_dir)
    sprite_id = fill_sprite_id if fill_sprite_id is not None else background_fill_sprite_id_for_level(level_number)
    if not (0 <= sprite_id < len(fill_sprites)):
        return Image.new("RGBA", (width, height), (0, 43, 48, 255))

    tile = fill_sprites[sprite_id].convert("RGBA")
    if tile.width <= 0 or tile.height <= 0:
        return Image.new("RGBA", (width, height), (0, 43, 48, 255))

    background = Image.new("RGBA", (width, height), (0, 43, 48, 255))
    for y in range(0, height, tile.height):
        for x in range(0, width, tile.width):
            background.alpha_composite(tile, (x, y))
    return background


def make_level_preview(data_dir: Path, number: int = 2, view: str = "bricks", scale: int = 3, level_override: RenderLevel | None = None) -> Image.Image:
    """
    Raw diagnostic grid view.

    Supported views:
      - "spells" / "logic0": low bytes from the render word grid
      - "bricks" / "logic1": high bytes from the render word grid
      - "visual": raw KE_LVL.DIG visual grid (kept only for CLI compatibility)
    """
    levels = load_level_set(data_dir)
    number = max(1, min(number, levels.level_count))
    palette = _palette_for(data_dir)

    if view in ("spells", "logic0"):
        if level_override is not None:
            cells = bytes(cell.flags for cell in level_override.cells)
        else:
            layer_index = 0
            cells = levels.logic_levels[number - 1].layers[layer_index]
        title = f"Level {number:02d} spells / low-byte codes"
    elif view in ("bricks", "logic1"):
        if level_override is not None:
            cells = bytes(cell.brick_id for cell in level_override.cells)
        else:
            layer_index = 1
            cells = levels.logic_levels[number - 1].layers[layer_index]
        title = f"Level {number:02d} bricks / high-byte ids"
    else:
        cells = levels.visual_levels[number - 1].cells
        title = f"Level {number:02d} KE_LVL.DIG visual/debug grid"

    cell_w = 28
    cell_h = 22
    margin = 12
    title_h = 22
    image = Image.new(
        "RGB",
        (margin * 2 + BRICK_GRID_WIDTH * cell_w, margin * 2 + title_h + BRICK_GRID_HEIGHT * cell_h),
        (18, 18, 18),
    )
    draw = ImageDraw.Draw(image)
    draw.text((margin, margin), title, fill=(230, 230, 230))

    for y in range(BRICK_GRID_HEIGHT):
        for x in range(BRICK_GRID_WIDTH):
            value = cells[y * BRICK_GRID_WIDTH + x]
            color = (20, 20, 20) if value == 0 else palette[value % len(palette)]
            x0 = margin + x * cell_w
            y0 = margin + title_h + y * cell_h
            draw.rectangle((x0, y0, x0 + cell_w - 2, y0 + cell_h - 2), fill=color, outline=(70, 70, 70))
            text_color = (255, 255, 255) if sum(color) < 280 else (0, 0, 0)
            draw.text((x0 + 4, y0 + 5), f"{value:02x}", fill=text_color)

    if scale != 1:
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    return image


def _draw_grid_overlay(draw: ImageDraw.ImageDraw, scale: int) -> None:
    for y in range(BRICK_GRID_HEIGHT):
        for x in range(BRICK_GRID_WIDTH):
            x0 = x * BRICK_STEP_W * scale
            y0 = y * BRICK_STEP_H * scale
            x1 = x0 + BRICK_STEP_W * scale - 1
            y1 = y0 + BRICK_STEP_H * scale - 1
            draw.rectangle((x0, y0, x1, y1), outline=(0, 105, 115, 255))


def _draw_id_overlay(draw: ImageDraw.ImageDraw, x0: int, y0: int, cell_w: int, label: str) -> None:
    pad_x = 2
    pad_y = 1
    box_w = max(12, len(label) * 6 + pad_x * 2)
    box_h = 11
    draw.rectangle((x0, y0, x0 + min(cell_w - 1, box_w), y0 + box_h), fill=(0, 0, 0, 190))
    draw.text((x0 + pad_x, y0 + pad_y), label, fill=(255, 255, 0, 255))


def make_game_level_preview(
    data_dir: Path,
    number: int = 2,
    scale: int = 4,
    show_grid: bool = False,
    show_ids: bool = False,
    show_spells: bool = False,
    show_background: bool = True,
    level_override: RenderLevel | None = None,
    background_fill_sprite_id: int | None = None,
) -> Image.Image:
    """
    Render gameplay brick grid using KE_BRICK.BOB.

    The game image is rendered cleanly at native scale, then scaled; ids, spell
    icons, and grid are drawn afterwards as readable overlays.
    """
    if level_override is None:
        render_levels = parse_render_levels(data_dir / "KE_LDCWC.TAB")
        number = max(1, min(number, len(render_levels)))
        level = render_levels[number - 1]
    else:
        level = level_override
        number = level.number

    brick_sprites, _ = decode_bob_sprites(data_dir / "KE_BRICK.BOB", data_dir)
    spell_sprites = []
    if show_spells:
        spell_sprites, _ = decode_bob_sprites(data_dir / "KE_SPELL.BOB", data_dir)

    base_width = BRICK_GRID_WIDTH * BRICK_STEP_W
    base_height = BRICK_GRID_HEIGHT * BRICK_STEP_H
    if show_background:
        base = make_background_grid(
            data_dir,
            number,
            base_width,
            base_height,
            fill_sprite_id=background_fill_sprite_id,
        )
    else:
        base = Image.new("RGBA", (base_width, base_height), (0, 43, 48, 255))

    for cell in level.cells:
        x0 = cell.x * BRICK_STEP_W
        y0 = cell.y * BRICK_STEP_H
        sprite_id = cell.brick_sprite_id
        if sprite_id is not None and 0 <= sprite_id < len(brick_sprites):
            base.alpha_composite(brick_sprites[sprite_id].convert("RGBA"), (x0, y0))

    image = base.resize((base.width * scale, base.height * scale), Image.Resampling.NEAREST) if scale != 1 else base.copy()
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    if show_grid:
        _draw_grid_overlay(draw, scale)

    cell_w = BRICK_STEP_W * scale
    cell_h = BRICK_STEP_H * scale

    for cell in level.cells:
        x0 = cell.x * cell_w
        y0 = cell.y * cell_h
        sprite_id = cell.brick_sprite_id

        if show_ids:
            label = ""
            if sprite_id is not None:
                label = str(sprite_id)
            elif cell.raw_word:
                label = f"-/{cell.flags}"
            if label:
                _draw_id_overlay(draw, x0, y0, cell_w, label)

        if show_spells and cell.powerup_code is not None:
            spell_sprite_index = cell.powerup_spell_bob_sprite_index
            if spell_sprite_index is not None and 0 <= spell_sprite_index < len(spell_sprites):
                icon = spell_sprites[spell_sprite_index].convert("RGBA")
                max_w = max(10, int(cell_w * 0.62))
                max_h = max(10, int(cell_h * 0.62))
                ratio = min(max_w / icon.width, max_h / icon.height)
                new_size = (max(1, int(icon.width * ratio)), max(1, int(icon.height * ratio)))
                icon = icon.resize(new_size, Image.Resampling.NEAREST)
                bx0 = x0 + (cell_w - icon.width) // 2 - 2
                by0 = y0 + (cell_h - icon.height) // 2 - 2
                bx1 = bx0 + icon.width + 3
                by1 = by0 + icon.height + 3
                draw.rectangle((bx0, by0, bx1, by1), fill=(0, 0, 0, 170), outline=(255, 220, 0, 255))
                overlay.alpha_composite(icon, (bx0 + 2, by0 + 2))

    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def save_level_preview(data_dir: Path, out_dir: Path, number: int = 2, view: str = "bricks", scale: int = 3) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    image = make_level_preview(data_dir, number=number, view=view, scale=scale)
    out_path = out_dir / f"level_{number:02d}_{view}.png"
    image.save(out_path)
    return out_path


def save_game_level_preview(data_dir: Path, out_dir: Path, number: int = 2, scale: int = 4) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    image = make_game_level_preview(data_dir, number=number, scale=scale)
    out_path = out_dir / f"level_{number:02d}_game_bricks.png"
    image.save(out_path)
    return out_path
