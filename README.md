# Krypton Egg reverse editor starter

Early Python reverse-engineering scaffold for Krypton Egg.

## Run the GUI

```bash
python run_gui.py --data-dir game_data
```

or:

```bash
python -m kegg.cli gui --data-dir game_data
```

The GUI currently has tabs for:

- **Level View**: a Level 02 calibration mock until the real level tables are found.
- **Sprite Atlas**: decoded GIF preview and raw BOB debug previews.
- **Notes**: reverse-engineering notes from `docs/`.

## Command line tools

```bash
python -m kegg.cli scan --data-dir game_data
python -m kegg.cli extract-images --data-dir game_data --out output/images
python -m kegg.cli analyze-bob --data-dir game_data --out output/bob
python -m kegg.cli export-bob-previews --data-dir game_data --out output/bob_previews
python -m kegg.cli extract-exe --exe game_data/KE.EXE --out output/exe
```

## Current findings

Most game data files use a `COD2` wrapper. The wrapper decode is implemented. GIF files decode cleanly. BOB files decode through the wrapper and expose plausible headers, but the exact sprite/RLE blitter is still unsolved.

The project is structured so that the GUI can grow incrementally as formats are solved.


## Current cleaned status

The project now uses the confirmed TW4 BOB decoder in `kegg/formats/bob_decode.py`.

Removed from the main code path:
- old `chunk4_probe`
- `best_effort`
- BOB workbench / diagnostics experiments
- fixed-only fallback experiments

Useful commands:

```bash
python -m kegg.cli export-bob-previews --data-dir game_data --out output/bob_previews
python -m kegg.cli export-graphics-atlas --data-dir game_data --out output/graphics
python run_gui.py --data-dir game_data
```
