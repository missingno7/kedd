# Level metadata decoded so far

## KE_LDCWC.TAB record header

Each level record is 586 bytes:

```text
0x000..0x001  u16 raw enemy spawn countdown / timer (inferred)
0x002..0x009  8 enemy type bytes
0x00a..0x225  18x15 word grid
0x226..0x249  remaining tail data, still unresolved
```

The first two bytes are loaded by `KE.EXE` into `ds:0xddb0` and later copied
into `ds:0xddd0` as a countdown. This strongly suggests an enemy spawn timer /
cadence value, but the exact time unit is not yet named.

The eight bytes at record offsets `+2..+9` are copied to memory at `0xa988`.
The game cycles through them while spawning enemies.

## Enemy ID mapping

The game uses the stored byte directly as an enemy type index:

```text
0 -> Enemy 0
1 -> Enemy 1
2 -> Enemy 2
3 -> Enemy 3
4 -> Enemy 4
5 -> Enemy 5
6 -> Enemy 6
7 -> Enemy 7
```

This comes from the spawn flow in `KE.EXE`:

```text
read level-header enemy byte
clamp to 0..7
use it directly to index the animation table at DS:0x6790
```

So there is no 1-based offset for enemy IDs.

The EXE animation table maps the enemy types to `KE_NMY.BOB` frames:

```text
Enemy 0 -> 0,1
Enemy 1 -> 2,3,4,3
Enemy 2 -> 5,5,5,5,6,7,64,65,64,7,6
Enemy 3 -> 8,9,10
Enemy 4 -> 11,12,13,12
Enemy 5 -> 14,15,16,15
Enemy 6 -> 17,18,19,20,21,22
Enemy 7 -> 23,24,25,26,27,28,29,30
```

The editor shows each enemy spawn slot as an image card instead of a raw number.

## Background table

Background choice is not stored in the `KE_LDCWC.TAB` record. `KE.EXE` keeps a
41-entry pointer table for background fillers:

```text
EXE table slot 0  -> KE_FILL sprite 6
EXE table slot 1  -> KE_FILL sprite 7
...
EXE table slot 40 -> KE_FILL sprite 46
```

The game increments the background slot when a new level is entered and wraps
after 41 slots. The editor locates this pointer table in `KE.EXE` and lets the
Level Metadata tab change the KE_FILL sprite used by each slot.

Because of the wrap, editing the background for level `N` also affects level
`N + 41`.
