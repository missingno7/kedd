from __future__ import annotations

import argparse
from pathlib import Path
import json

from PIL import Image

from .formats.bob import dump_bob_analysis, parse_bob_header
from .formats.cod import decode_file
from .formats.le import extract_le_objects
from .formats.level import load_level_set, format_grid
from .graphics.level_preview import save_level_preview, save_game_level_preview
from .graphics.bob_preview import save_raw_bob_atlas
from .graphics.assets import build_graphics_overview
from .graphics.powerup_preview import build_powerup_report, export_powerup_analysis


def command_scan(args: argparse.Namespace) -> None:
    data_dir = Path(args.data_dir)
    rows = []
    for path in sorted(p for p in data_dir.iterdir() if p.is_file()):
        result = decode_file(path)
        rows.append(
            {
                "file": path.name,
                "size": path.stat().st_size,
                "codec": result.codec,
                "checksum_ok": result.checksum_ok,
                "decoded_head_ascii": result.data[:16].decode("latin1", errors="replace"),
                "decoded_head_hex": result.data[:16].hex(),
            }
        )
    print(json.dumps(rows, indent=2))


def command_extract_images(args: argparse.Namespace) -> None:
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for path in sorted(data_dir.glob("*")):
        if not path.is_file():
            continue
        result = decode_file(path)
        decoded_path = out_dir / f"{path.stem}.decoded{path.suffix.lower()}"
        decoded_path.write_bytes(result.data)

        if result.data.startswith(b"GIF8"):
            gif_path = out_dir / f"{path.stem}.gif"
            gif_path.write_bytes(result.data)
            image = Image.open(gif_path)
            png_path = out_dir / f"{path.stem}.png"
            image.save(png_path)
            print(f"decoded image: {path.name} -> {png_path}")


def command_analyze_bob(args: argparse.Namespace) -> None:
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out)
    dump_bob_analysis(data_dir, out_dir)
    for path in sorted(data_dir.glob("*.BOB")):
        print(parse_bob_header(path))


def command_extract_exe(args: argparse.Namespace) -> None:
    summary = extract_le_objects(Path(args.exe), Path(args.out), write_disassembly=not args.no_disasm)
    print(summary)


def command_export_bob_previews(args: argparse.Namespace) -> None:
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out)
    for path in sorted(data_dir.glob("*.BOB")):
        out_path = save_raw_bob_atlas(path, data_dir=data_dir, out_dir=out_dir, scale=args.scale)
        print(f"BOB atlas: {path.name} -> {out_path}")


def command_export_graphics_atlas(args: argparse.Namespace) -> None:
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out)
    out_path = build_graphics_overview(data_dir, out_dir)
    print(f"graphics overview: {out_path}")



def command_analyze_powerups(args: argparse.Namespace) -> None:
    data_dir = Path(args.data_dir)
    report = build_powerup_report(data_dir)
    # Do not print every cell by default; the full JSON is available through export-powerups.
    summary = {
        "interpretation": report["interpretation"],
        "powerup_spell_range": report["powerup_spell_range"],
        "total_powerup_cells": report["total_powerup_cells"],
        "counts_by_powerup_code": report.get("counts_by_powerup_code", {}),
        "counts_by_logical_spell": report.get("counts_by_logical_spell", {}),
        "counts_by_level": report["counts_by_level"],
    }
    print(json.dumps(summary, indent=2))


def command_export_powerups(args: argparse.Namespace) -> None:
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out)
    out_path = export_powerup_analysis(data_dir, out_dir, level=args.level)
    print(f"powerup preview: {out_path}")


def command_analyze_levels(args: argparse.Namespace) -> None:
    data_dir = Path(args.data_dir)
    levels = load_level_set(data_dir)
    print(f"KE_LVL.DIG header: {levels.visual_header.hex(' ')}")
    print(f"visual levels: {len(levels.visual_levels)}")
    print(f"logic levels: {len(levels.logic_levels)}")
    level_number = max(1, min(args.level, levels.level_count))
    visual = levels.visual_levels[level_number - 1]
    print(f"\nLevel {level_number} visual grid ({len(visual.cells)} bytes = 18 x 15):")
    print(format_grid(visual.rows()))
    if level_number <= len(levels.logic_levels):
        logic = levels.logic_levels[level_number - 1]
        for idx, layer in enumerate(logic.layers):
            nonzero = sum(1 for value in layer if value)
            print(f"\nLevel {level_number} logic layer {idx}: nonzero cells = {nonzero}")
            print(format_grid(logic.layer_rows(idx)))
        print(f"\nLevel {level_number} logic tail ({len(logic.tail)} bytes): {logic.tail.hex(' ')}")


def command_export_level_previews(args: argparse.Namespace) -> None:
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    levels = load_level_set(data_dir)
    if args.all:
        numbers = range(1, len(levels.visual_levels) + 1)
    else:
        numbers = [args.level]
    for number in numbers:
        if args.view == "game":
            out_path = save_game_level_preview(data_dir, out_dir, number=number, scale=args.scale)
        else:
            out_path = save_level_preview(data_dir, out_dir, number=number, view=args.view, scale=args.scale)
        print(f"level preview: {out_path}")


def command_gui(args: argparse.Namespace) -> None:
    from .gui.app import main as gui_main

    gui_main(["--data-dir", args.data_dir])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Krypton Egg reverse-engineering helper tools")
    sub = parser.add_subparsers(required=True)

    scan = sub.add_parser("scan", help="Scan files and show COD decode status")
    scan.add_argument("--data-dir", default="game_data")
    scan.set_defaults(func=command_scan)

    images = sub.add_parser("extract-images", help="Decode COD files and export valid GIFs as PNG")
    images.add_argument("--data-dir", default="game_data")
    images.add_argument("--out", default="output/images")
    images.set_defaults(func=command_extract_images)

    bob = sub.add_parser("analyze-bob", help="Dump inferred BOB headers")
    bob.add_argument("--data-dir", default="game_data")
    bob.add_argument("--out", default="output/bob")
    bob.set_defaults(func=command_analyze_bob)

    exe = sub.add_parser("extract-exe", help="Extract LE objects from KE.EXE")
    exe.add_argument("--exe", default="game_data/KE.EXE")
    exe.add_argument("--out", default="output/exe")
    exe.add_argument("--no-disasm", action="store_true")
    exe.set_defaults(func=command_extract_exe)

    bob_previews = sub.add_parser("export-bob-previews", help="Export decoded BOB sprite atlases")
    bob_previews.add_argument("--data-dir", default="game_data")
    bob_previews.add_argument("--out", default="output/bob_previews")
    bob_previews.add_argument("--scale", type=int, default=3)
    bob_previews.set_defaults(func=command_export_bob_previews)

    graphics = sub.add_parser("export-graphics-atlas", help="Export a combined overview of decoded graphics")
    graphics.add_argument("--data-dir", default="game_data")
    graphics.add_argument("--out", default="output/graphics")
    graphics.set_defaults(func=command_export_graphics_atlas)

    powerups = sub.add_parser("analyze-powerups", help="Analyze powerup drops encoded in level cell metadata")
    powerups.add_argument("--data-dir", default="game_data")
    powerups.set_defaults(func=command_analyze_powerups)

    export_powerups = sub.add_parser("export-powerups", help="Export powerup/drop overlays for level grids")
    export_powerups.add_argument("--data-dir", default="game_data")
    export_powerups.add_argument("--out", default="output/powerups")
    export_powerups.add_argument("--level", type=int, default=None)
    export_powerups.set_defaults(func=command_export_powerups)

    levels = sub.add_parser("analyze-levels", help="Parse KE_LVL.DIG and KE_LDCWC.TAB as level grids")
    levels.add_argument("--data-dir", default="game_data")
    levels.add_argument("--level", type=int, default=2)
    levels.set_defaults(func=command_analyze_levels)

    level_previews = sub.add_parser("export-level-previews", help="Export PNG previews of parsed level grids")
    level_previews.add_argument("--data-dir", default="game_data")
    level_previews.add_argument("--out", default="output/levels")
    level_previews.add_argument("--level", type=int, default=2)
    level_previews.add_argument("--all", action="store_true")
    level_previews.add_argument("--view", choices=["visual", "logic0", "logic1", "logic2", "game"], default="game")
    level_previews.add_argument("--scale", type=int, default=3)
    level_previews.set_defaults(func=command_export_level_previews)

    gui = sub.add_parser("gui", help="Launch the tabbed reverse-editor GUI")
    gui.add_argument("--data-dir", default="game_data")
    gui.set_defaults(func=command_gui)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
