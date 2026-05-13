# Editor + background rendering

## Level View editing

The Level View is now an editor.

Right-side editor tabs:

- **Bricks**: image palette from `KE_BRICK.BOB`
  - left click in the level inserts/replaces the selected brick
  - right click clears the whole cell
- **Spells**: image palette of EXE-derived logical drop types
  - left click writes the selected spell/drop metadata into the cell
  - right click removes only the spell/drop metadata

The editor has a **Save levels** button. It writes `KE_LDCWC.TAB` back using the original COD2 wrapper and creates `KE_LDCWC.TAB.bak` on the first save.

## Background rendering

The gameplay preview now tiles the background for the current level from `KE_FILL.BOB`.

Reverse-engineering note from `KE.EXE`:
- a fill-sprite pointer table at `DS:0x2E9C` references `KE_FILL.BOB` sprites `6..46`
- the background index increments per level and wraps after `0x29 = 41` entries

Current mapping:

```text
level 1  -> KE_FILL sprite 6
level 2  -> KE_FILL sprite 7
...
level 41 -> KE_FILL sprite 46
level 42 -> KE_FILL sprite 6
```
