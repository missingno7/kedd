# Level data notes

The gameplay screenshot confirms that the visible brick/playfield grid is **18 x 15**. The earlier 25 x 11 parse was a false-but-tempting interpretation of the 275-byte record size.

## KE_LVL.DIG

After COD2 decoding, `KE_LVL.DIG` is exactly:

```text
4-byte global header: 10 00 00 03
40 level records
1 level record = 275 bytes
275 = 18 x 15 cells + 5 unknown bytes
```

Current parser therefore treats each record as:

```text
cells: 270 bytes = 18 x 15
extra: 5 bytes
```

Important: these cell values are **not yet proven to be direct KE_BRICK.BOB indices**. Rendering them directly through the brick atlas produces recognizable bricks but not the real gameplay level. So this is likely visual/color/gradient/shading data, or one part of a combined level format.

## KE_LDCWC.TAB

After COD2 decoding, `KE_LDCWC.TAB` is exactly:

```text
40 records
1 record = 879 bytes
879 = 3 x 270 + 69
```

Current parser per level:

```text
layer 0: 18 x 15 cells
layer 1: 18 x 15 cells
layer 2: 18 x 15 cells
tail:    69 bytes
```

Layer meanings are not solved yet. They are good candidates for collision/material state, special flags, hidden powerups, or other gameplay metadata.

## Current visual status

- `KE_BRICK.BOB` is now decoded well enough to show real brick sprites.
- The visible level grid is confirmed as 18 x 15.
- Directly mapping level bytes to brick sprite indices is still wrong.
- The next missing piece is the mapping/combination logic between level cells, brick graphics, color/gradient variants, and hidden powerups.

## 2026-05-10 update: renderable brick grid in KE_LDCWC.TAB

The first render path that visually matches gameplay screenshots is not `KE_LVL.DIG` as a byte grid.

Current best hypothesis:

```text
KE_LDCWC.TAB record size: 879 bytes
record byte offset 339:
  18 x 15 cells
  each cell = uint16 little-endian raw word
  high byte = visible KE_BRICK.BOB sprite id
  low byte  = unresolved per-cell metadata / flags / possible powerup info
```

Example from the pyramid screenshot:

```text
0x0900 -> brick sprite 0x09, flags 0x00
0x3920 -> brick sprite 0x39, flags 0x20
0x3d50 -> brick sprite 0x3d, flags 0x50
```

This explains the many colors: they are not dynamically recolored bricks. The color variants already exist as separate entries in `KE_BRICK.BOB`, and the level cell selects them by brick id.

Still unresolved:

- exact game-level ordering vs record ordering
- low-byte flag meanings
- whether low-byte values encode powerups, hit points, scripted effects, or spawn/drop metadata
- how the background/fill/pavement layer is selected
