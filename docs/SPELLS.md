# Spell / powerup mapping

This is now decoded from the game logic in `KE.EXE`, not guessed from the visual atlas.

## Key point

`KE_SPELL.BOB` frame ids `24..73` are visual animation frames.

The level cell low byte is **not** a direct `KE_SPELL.BOB` frame id. The game decodes it as:

```text
drop_type = (low_byte >> 2) - 1
variant   = low_byte & 0x03
```

Then `drop_type` indexes an animation table at `DS:0x60F0` in `KE.EXE`.

## EXE drop_type -> KE_SPELL.BOB frames

```text
00 -> 52,53,54,55,56,55,54,53    Grow racket
01 -> 57                         Knife
02 -> 43                         Score X2
03 -> 40,41,42                   Drunk
04 -> 66,67,68,69,70,69,68,67    Shrink ball
05 -> 60                         Glue
06 -> 27                         Extra life
07 -> 38                         Extra ball
08 -> 47,48,49,50,51,50,49,48    Grow ball
09 -> 24                         Darkness / Blind
10 -> 59                         Fast ball
11 -> 58                         Slow ball
12 -> 46                         AI racket
13 -> 44,45                      Jetpack
14 -> 31                         Cage
15 -> 25                         Protection
16 -> 36                         Plasma blast
17 -> 28,29                      Super ball
18 -> 30                         Dum ball
19 -> 39                         Pontoon
20 -> 37                         Fast plasma blast
21 -> 26                         Random spell
22 -> 61,62,63,64,65,64,63,62    Shrink racket
23 -> 32                         Straight shot
24 -> 34                         Wide shot
25 -> 33                         Fast straight shot
26 -> 35                         Fast wide shot
27 -> 71,72,73                   Unknown visual spell
```

## Verified examples

```text
L1 X8  Y8 : low=0x22 -> drop_type 07 -> frame 38 -> Extra ball
L1 X12 Y10: low=0x04 -> drop_type 00 -> frames 52..56 -> Grow racket
L1 X0  Y2 : low=0x38 -> drop_type 13 -> frames 44..45 -> Jetpack
L1 X16 Y1 : low=0x28 -> drop_type 09 -> frame 24 -> Darkness / Blind
L1 X16 Y7 : low=0x3C -> drop_type 14 -> frame 31 -> Cage
L1 X4  Y4 : low=0x5A -> drop_type 21 -> frame 26 -> Random spell
L1 X12 Y4 : low=0x5A -> drop_type 21 -> frame 26 -> Random spell
```

## Cage off-by-one note

The visual cage frame is `KE_SPELL.BOB` frame `31`.

If a UI shows cage as `32`, that is an off-by-one or an old direct-id interpretation. The correct EXE-derived path is:

```text
low byte 0x3C -> drop_type 14 -> visual frame 31 -> Cage
```


## Visual frame vs actual BOB record index

The game/editor spell frame ids used in notes are `24..73`, but the actual
`KE_SPELL.BOB` records used by the EXE animation table are `34..83`.

So for drawing the icon:

```text
actual KE_SPELL.BOB record index = game spell frame + 10
```

Examples:

```text
Darkness:    game frame 24 -> actual KE_SPELL.BOB record 34
Grow racket: game frame 52 -> actual KE_SPELL.BOB record 62
Cage:        game frame 31 -> actual KE_SPELL.BOB record 41
```

This fixes the apparent "off by 10" display bug where Darkness looked like
frame 14 and Grow racket looked like frame 42.

## Brick classes

Current level-data convention:

```text
KE_BRICK image 0-47      normal breakable, no spell marker
KE_BRICK image 48-95     breakable with powerup marker / dot
KE_BRICK image 96-143    normal breakable, no spell marker
KE_BRICK image 144-246   unbreakable
KE_BRICK image 247-248   portal sides
KE_BRICK image 249-255   respawning
```

The brick image does not determine which spell is inside, but in the game data
hidden spells are expected only on the dotted breakable bricks `48..95`.
