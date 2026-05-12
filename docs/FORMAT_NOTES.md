# Format notes

## COD2 wrapper

Most game assets end with a `COD2` trailer. Decoding is implemented in `kegg/formats/cod.py`.

COD2 trailer:

```text
uint16 checksum
uint16 key_seed_word
char[4] marker = "COD2"
```

The executable decoder XOR-decodes the first `min(payload_len, 0x400)` bytes with a rotating 32-bit key derived from the seed word. This recovers normal GIF headers such as `GIF87a`.

## BOB files

BOB files are decoded from COD2 first. They are sequences of sprite records, not one flat bitmap.

Observed structure:

```text
uint16 object_count
object records...
```

Each object record starts with:

```text
uint16 record_size
uint16 width
uint16 height
uint16 header_size   ; observed 0x001c
uint16 format_word   ; observed 0x0305
int16  bounds_left
int16  bounds_top
int16  bounds_right
int16  bounds_bottom
... offsets / draw data ...
```

Examples:

```text
KE_BRICK.BOB : 256 sprites, mostly 15 x 8
KE_DIGIT.BOB : 10 sprites, 7 x 8
KE_FONT.BOB  : 98 sprites, 10 x 12
KE_RACK.BOB  : 49 sprites, variable paddle / rack sprites
```

The exact RLE/blitter command stream is not fully solved yet. The project therefore still renders BOB files as debug previews, not as real sprites.

## Level files

See `docs/LEVEL_NOTES.md` for the current level-grid parse.
