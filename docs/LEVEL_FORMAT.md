# Level format correction

`KE_LDCWC.TAB` is:

```text
35160 bytes = 60 * 586
```

Each level record is:

```text
0x000..0x009  10 bytes metadata/header
0x00a..0x225  18x15 little-endian word grid = 540 bytes
0x226..0x249  36 bytes tail/extra data
```

The previous parser used offset `46`, which skipped the first 36 bytes of the grid. That is exactly one row of 18 little-endian words, so level 1 appeared to be missing the first row of bricks.

Correct cell interpretation:

```text
word = little-endian u16
high byte = 1-based KE_BRICK.BOB sprite id
low byte  = per-cell metadata / KE_SPELL.BOB powerup frame id
```

Rendering rule:

```text
if high byte == 0:
    empty
else:
    KE_BRICK.BOB image index = high byte - 1
```
