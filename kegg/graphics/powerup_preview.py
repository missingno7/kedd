from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw

from kegg.formats.bob_decode import decode_bob_sprites
from kegg.formats.level import (
    BRICK_GRID_HEIGHT,
    BRICK_GRID_WIDTH,
    POWERUP_SPELL_ID_MAX,
    POWERUP_SPELL_ID_MIN,
    SPELL_DROP_TYPE_TO_FRAMES,
    SPELL_RANGES,
    RenderCell,
    is_powerup_spell_id,
    parse_render_levels,
)


def collect_powerup_cells(data_dir: Path) -> list[dict]:
    levels = parse_render_levels(data_dir / "KE_LDCWC.TAB")
    rows: list[dict] = []
    for level in levels:
        for cell in level.cells:
            powerup = cell.powerup_spell_id
            if cell.powerup_code is None:
                continue
            rows.append(
                {
                    "level": level.number,
                    "x": cell.x,
                    "y": cell.y,
                    "raw_word": cell.raw_word,
                    "brick_id": cell.brick_id,
                    "brick_sprite_id": cell.brick_sprite_id,
                    "brick_class": cell.brick_class,
                    "can_contain_powerup": cell.can_contain_powerup,
                    "cell_low_byte": cell.flags,
                    "powerup_code": cell.powerup_code,
                    "drop_type": cell.powerup_drop_type,
                    "variant": cell.powerup_variant,
                    "representative_spell_frame": powerup,
                    "representative_bob_sprite_index": cell.powerup_spell_bob_sprite_index,
                    "spell_frames": cell.powerup_frames,
                    "logical_spell": cell.powerup_spell_name,
                }
            )
    return rows


def build_powerup_report(data_dir: Path) -> dict:
    cells = collect_powerup_cells(data_dir)
    by_id = Counter(row["powerup_code"] for row in cells)
    by_logical = Counter(row["logical_spell"] for row in cells)
    by_level = Counter(row["level"] for row in cells)
    invalid_powerup_carriers = [row for row in cells if not row["can_contain_powerup"]]
    return {
        "interpretation": (
            "KE.EXE decodes the level cell low byte as a drop code, not a direct KE_SPELL.BOB frame. "
            "drop_type = (low_byte >> 2) - 1, variant = low_byte & 3. "
            "drop_type indexes the EXE animation table at DS:0x60F0, which maps to KE_SPELL.BOB frames 24..73."
        ),
        "powerup_spell_range": [POWERUP_SPELL_ID_MIN, POWERUP_SPELL_ID_MAX],
        "total_powerup_cells": len(cells),
        "spell_ranges": [{"start": start, "end": end, "name": name} for start, end, name in SPELL_RANGES],
        "drop_type_to_frames": {str(k): v for k, v in sorted(SPELL_DROP_TYPE_TO_FRAMES.items())},
        "counts_by_powerup_code": {str(k): v for k, v in sorted(by_id.items())},
        "counts_by_logical_spell": {str(k): v for k, v in sorted(by_logical.items())},
        "counts_by_level": {str(k): v for k, v in sorted(by_level.items())},
        "invalid_powerup_carriers": invalid_powerup_carriers,
        "invalid_powerup_carrier_count": len(invalid_powerup_carriers),
        "cells": cells,
    }


def make_spell_powerup_sheet(data_dir: Path, scale: int = 4, columns: int = 10) -> Image.Image:
    sprites, _ = decode_bob_sprites(data_dir / "KE_SPELL.BOB", data_dir)
    ids = list(range(POWERUP_SPELL_ID_MIN, min(POWERUP_SPELL_ID_MAX, len(sprites) - 1) + 1))
    images = [sprites[i].convert("RGBA") for i in ids]
    labels = [str(i) for i in ids]
    if not images:
        return Image.new("RGB", (320, 120), (18, 18, 22))

    max_w = max(image.width for image in images)
    max_h = max(image.height for image in images)
    gap = 8
    label_h = 14
    rows = (len(images) + columns - 1) // columns
    canvas = Image.new("RGBA", (columns * (max_w * scale + gap * 2), rows * (max_h * scale + gap * 2 + label_h)), (18, 18, 22, 255))
    draw = ImageDraw.Draw(canvas)

    for n, (image, label) in enumerate(zip(images, labels)):
        x = (n % columns) * (max_w * scale + gap * 2) + gap
        y = (n // columns) * (max_h * scale + gap * 2 + label_h) + gap
        scaled = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
        canvas.alpha_composite(scaled, (x, y))
        draw.rectangle((x - 1, y - 1, x + scaled.width, y + scaled.height), outline=(80, 80, 90, 255))
        draw.text((x, y + max_h * scale + 2), label, fill=(230, 230, 230, 255))

    return canvas.convert("RGB")


def make_powerup_overlay(data_dir: Path, level_number: int, scale: int = 4) -> Image.Image:
    """Render brick grid with KE_SPELL powerup icons over cells that contain drops."""
    render_levels = parse_render_levels(data_dir / "KE_LDCWC.TAB")
    level_number = max(1, min(level_number, len(render_levels)))
    level = render_levels[level_number - 1]

    brick_sprites, _ = decode_bob_sprites(data_dir / "KE_BRICK.BOB", data_dir)
    spell_sprites, _ = decode_bob_sprites(data_dir / "KE_SPELL.BOB", data_dir)

    brick_w = 16
    brick_h = 9
    icon_box_h = 18

    image = Image.new("RGBA", (BRICK_GRID_WIDTH * brick_w, BRICK_GRID_HEIGHT * (brick_h + icon_box_h)), (0, 43, 48, 255))
    draw = ImageDraw.Draw(image)

    for cell in level.cells:
        x0 = cell.x * brick_w
        y0 = cell.y * (brick_h + icon_box_h)
        sprite_id = cell.brick_sprite_id
        if sprite_id is not None and 0 <= sprite_id < len(brick_sprites):
            image.alpha_composite(brick_sprites[sprite_id].convert("RGBA"), (x0, y0))

        powerup = cell.powerup_spell_bob_sprite_index
        if powerup is not None and 0 <= powerup < len(spell_sprites):
            icon = spell_sprites[powerup].convert("RGBA")
            # Fit icon into a small preview box under the brick.
            max_w = brick_w
            max_h = icon_box_h - 2
            if icon.width > max_w or icon.height > max_h:
                ratio = min(max_w / icon.width, max_h / icon.height)
                icon = icon.resize((max(1, int(icon.width * ratio)), max(1, int(icon.height * ratio))), Image.Resampling.NEAREST)
            ix = x0 + (brick_w - icon.width) // 2
            iy = y0 + brick_h + (icon_box_h - icon.height) // 2
            image.alpha_composite(icon, (ix, iy))
            draw.text((x0 + 1, y0 + brick_h), str(powerup), fill=(255, 255, 0, 255))
        else:
            # faint empty marker, useful for grid debugging
            draw.rectangle((x0, y0 + brick_h, x0 + brick_w - 1, y0 + brick_h + icon_box_h - 1), outline=(0, 70, 75, 255))

    if scale != 1:
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    return image.convert("RGB")


def make_powerup_contact_sheet(data_dir: Path, scale: int = 2, columns: int = 5) -> Image.Image:
    levels = parse_render_levels(data_dir / "KE_LDCWC.TAB")
    previews = [make_powerup_overlay(data_dir, level.number, scale=1) for level in levels]
    labels = [f"Level {level.number:02d}" for level in levels]

    if not previews:
        return Image.new("RGB", (320, 120), (18, 18, 22))

    max_w = max(image.width for image in previews)
    max_h = max(image.height for image in previews)
    gap = 12
    label_h = 16
    rows = (len(previews) + columns - 1) // columns
    canvas = Image.new("RGB", (columns * (max_w * scale + gap * 2), rows * (max_h * scale + gap * 2 + label_h)), (10, 10, 14))
    draw = ImageDraw.Draw(canvas)

    for i, (image, label) in enumerate(zip(previews, labels)):
        x = (i % columns) * (max_w * scale + gap * 2) + gap
        y = (i // columns) * (max_h * scale + gap * 2 + label_h) + gap
        draw.text((x, y), label, fill=(235, 235, 235))
        scaled = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
        canvas.paste(scaled, (x, y + label_h))

    return canvas


def export_powerup_analysis(data_dir: Path, out_dir: Path, level: int | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    report = build_powerup_report(data_dir)
    report_path = out_dir / "powerup_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    make_spell_powerup_sheet(data_dir).save(out_dir / "ke_spell_powerups_24_73.png")

    if level is None:
        contact = make_powerup_contact_sheet(data_dir)
        out_path = out_dir / "powerup_levels_contact_sheet.png"
        contact.save(out_path)
    else:
        overlay = make_powerup_overlay(data_dir, level)
        out_path = out_dir / f"level_{level:02d}_powerups.png"
        overlay.save(out_path)

    return out_path
