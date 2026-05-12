# Krypton Egg BOB / TW4 format

This document contains the cleaned-up, confirmed understanding of the game's `.BOB` graphics format.

## Confirmed structure

A `.BOB` file is a list of variable-size sprite records:

```text
u16 record_count

repeat record_count:
    u16 record_size
    BOB record body
```

The body starts immediately after the `record_size` word:

```text
+0x00 u16 width
+0x02 u16 height
+0x04 u16 header_size          # observed 28
+0x06 u16 format_word          # observed 0x0305 = TW4
+0x08 i16 bounds/offset value
+0x0a i16 bounds/offset value
+0x0c i16 bounds/offset value
+0x0e i16 bounds/offset value
+0x10 u16 stream_offset[0]
+0x12 u16 stream_offset[1]
+0x14 u16 stream_offset[2]
+0x16 u16 stream_offset[3]
+0x18 u16 stream_offset[4]
+0x1a u16 extra/reserved
```

## The important fix

The original experiments were wrong because they treated the data payload as starting at:

```text
record_start + 2 + header_size
```

The game uses an internal BOB pointer that points to the record-size word itself, then adds `header_size`:

```text
stream_base = record_start + header_size
```

That two-byte difference is the reason simple bricks looked mostly correct while transparent/variable sprites were broken.

## TW4 row stream

Each of the four visible streams is a VGA plane stream:

```text
stream_start = record_start + header_size + stream_offset[plane]
```

Each scanline in a stream is encoded as commands:

```text
u8 command_count

repeat command_count:
    i8 n
    if n < 0:
        skip -n plane positions
    else:
        copy n palette bytes
```

Each copied byte belongs to one VGA plane:

```text
x = plane + plane_x * 4
```

This matches the blitter path found in `KE.EXE` around the routines that branch into the TW4/VGA blitter.
