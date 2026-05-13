# GUI Level View

Right-side notebook tabs:

- **Bricks** — image palette of `KE_BRICK.BOB`, left click places, right click erases a whole cell.
- **Spells** — image palette of logical EXE-derived drop types, left click writes spell metadata, right click removes only spell metadata.
- **Cell Inspector** — selected cell details.
- **Level Metadata** — editable level-level properties:
  - background KE_FILL sprite via the EXE background table
  - raw/inferred enemy spawn timer
  - eight enemy spawn-cycle slots shown as enemy image cards

Editing features:
- **Undo / Redo** buttons and shortcuts:
  - `Ctrl+Z`
  - `Ctrl+Y`
  - `Ctrl+Shift+Z`
- **Clear level** clears the full 18x15 brick/spell grid and is undoable.
- In the **Bricks** tab, dragging the left mouse button paints bricks and dragging the right mouse button erases cells.
- Map editing is intentionally active only in the `game` view.
- The main view uses a horizontal splitter, so the right editor panel can be widened.
- Brick/spell image palettes automatically reflow into more columns when the right panel is wider.

`Save data` writes:
- `KE_LDCWC.TAB` when level grid/metadata changed
- `KE.EXE` when the background table changed

Both files receive a `.bak` backup on first save.


Toolbar:
- The **Zoom** selector next to the level number controls the level preview scale.
- Available scales: `1x`, `2x`, `3x`, `4x`, `5x`, `6x`, `8x`.
