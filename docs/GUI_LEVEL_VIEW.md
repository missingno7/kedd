# GUI Level View

Recent cleanup:
- Removed the useless `game_data: game_data` label from the header.
- Removed the Render button; the view now updates automatically.
- View names are now user-friendly:
  - `game`
  - `spells` (old `logic0`, low-byte spell/drop codes)
  - `bricks` (old `logic1`, high-byte brick ids)
- The old `visual` view is no longer shown in the GUI.

Overlay behavior:
- Brick ids are drawn as an overlay on the already-scaled image.
- Spell icons are drawn as a smaller overlay on top of the already-scaled image.
- This keeps the gameplay pixels clean and makes debug overlays easier to read.
