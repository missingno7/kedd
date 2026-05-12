# Research notes

Cleaned-up project state:

- Removed old experimental `chunk4_probe`, `workbench`, `diagnostics`, and `best_effort` code.
- Kept the confirmed TW4 decoder in `kegg/formats/bob_decode.py`.
- `KE_BRICK.BOB`, `KE_DIGIT.BOB`, `KE_MONST.BOB`, `KE_NMY.BOB`, `KE_RACK.BOB`, `KE_SPELL.BOB`, and related BOBs now go through the same decoder.
- The older accidental fixed-row behavior is no longer needed.

Useful commands:

```bash
python -m kegg.cli export-bob-previews --data-dir game_data --out output/bob_previews
python -m kegg.cli export-graphics-atlas --data-dir game_data --out output/graphics
python -m kegg.cli export-level-previews --data-dir game_data --out output/levels --all --view game
python run_gui.py --data-dir game_data
```
