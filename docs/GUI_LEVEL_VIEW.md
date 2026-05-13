# GUI Level View

Right-side notebook tabs:

- **Bricks** — image palette of `KE_BRICK.BOB`, left click places, right click erases a whole cell.
- **Spells** — image palette of logical EXE-derived drop types, left click writes spell metadata, right click removes only spell metadata.
- **Cell Inspector** — selected cell details moved out of the main side panel into its own tab.
- **Level Metadata** — editable level-level properties:
  - background KE_FILL sprite via the EXE background table
  - raw/inferred enemy spawn timer
  - eight enemy spawn-cycle slots shown as enemy image cards

`Save data` writes:
- `KE_LDCWC.TAB` when level grid/metadata changed
- `KE.EXE` when the background table changed

Both files receive a `.bak` backup on first save.
