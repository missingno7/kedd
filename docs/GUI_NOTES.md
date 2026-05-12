# GUI structure

The editor is now intentionally structured like the previous reverse-engineering editor:

- `Level View` is the future gameplay/level renderer.
- `Sprite Atlas` is for browsing decoded GIFs and BOB sprite resources.
- `Notes` shows reverse-engineering notes directly inside the app.

Current state:

- GIF resources are decoded through the solved `COD2` wrapper and shown as real images.
- BOB resources are shown as **raw debug atlases**. This is not final sprite decoding yet; it is a visual aid while the real BOB blitter/RLE format is being located in the EXE disassembly.
- Level View currently renders a hand-authored Level 02 calibration mock based on the supplied gameplay screenshot. This keeps the GUI shape ready while the real level table is being found.

Planned GUI tabs:

1. Level View
   - level selector
   - real parsed brick grid
   - sprite-backed renderer
   - eventually editable cells / brick types

2. Sprite Atlas
   - BOB/GIF browser
   - decoded sprite atlas
   - selected sprite metadata
   - export PNG

3. Raw Data / Hex View
   - decoded COD payload preview
   - useful offsets
   - linked selections from atlas/level view

4. Disassembly Notes
   - known functions
   - suspected draw/blit routines
   - suspected level loading routines
