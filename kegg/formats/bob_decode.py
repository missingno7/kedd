from __future__ import annotations

import struct
from pathlib import Path
from typing import List, Tuple

from PIL import Image

from .cod import decode_file
from .palette import RGB, default_palette, load_vga_palette


def _palette_for(data_dir: Path) -> List[RGB]:
    pal = data_dir / "KE_ALL.PAL"
    if pal.exists():
        try:
            return load_vga_palette(pal)
        except Exception:
            pass
    return default_palette()


def _flat_palette(palette: List[RGB]) -> List[int]:
    out: List[int] = []
    for r, g, b in palette[:256]:
        out.extend((r, g, b))
    while len(out) < 768:
        out.extend((0, 0, 0))
    return out[:768]


def _s8(value: int) -> int:
    return value - 256 if value >= 128 else value


def _image_from_values(width: int, height: int, values: list[int], palette: list[int]) -> Image.Image:
    im = Image.new("P", (max(1, width), max(1, height)), 0)
    im.putpalette(palette)
    im.putdata(values[: width * height] + [0] * max(0, width * height - len(values)))
    return im


def _decode_tw4_rle_record(data: bytes, record_start: int, width: int, height: int, header_size: int, offsets: list[int], record_end: int, palette: list[int]) -> Image.Image:
    """Decode Krypton Egg's TW4/VGA BOB record.

    This is based on the KE.EXE blitter path around 0x222d1/0x2271d.

    Important detail:
    The internal ESI used by the game points at record_start + header_size,
    i.e. two bytes before the "payload" position we originally used.  The
    offset table is addressed relative to that position. This was the missing
    piece that made all non-rectangular BOBs look wrong.

    Per row / per plane stream:

        command_count: u8
        repeat command_count:
            n: i8
            if n < 0: skip -n bytes/pixels in this VGA plane row
            else: copy n palette bytes

    Each copied byte belongs to one VGA plane, so image x = plane + plane_x * 4.
    """
    values = [0] * (width * height)

    for plane in range(4):
        # EXE does: esi = record_start + header_size; then derives each plane
        # stream as esi - selector + word[esi-selector]. Algebraically this is
        # record_start + header_size + offsets[plane].
        pos = record_start + header_size + offsets[plane]
        end = record_end

        for y in range(height):
            if pos >= end:
                break

            command_count = data[pos]
            pos += 1
            cursor = 0

            # A malformed stream would desync; guard hard so previews never crash.
            for _ in range(command_count):
                if pos >= end:
                    break
                n = _s8(data[pos])
                pos += 1

                if n < 0:
                    cursor += -n
                else:
                    run = data[pos : pos + n]
                    pos += n
                    for k, value in enumerate(run):
                        x = plane + (cursor + k) * 4
                        if 0 <= x < width:
                            values[y * width + x] = value
                    cursor += n

    return _image_from_values(width, height, values, palette)


def decode_bob_sprites(path: Path, data_dir: Path) -> Tuple[List[Image.Image], list[dict]]:
    """Decode Krypton Egg BOB sprites.

    Current confirmed understanding:
      - The BOB record starts with a 2-byte record size.
      - The internal BOB pointer used by KE.EXE points to this record start.
      - [record+2]  = width
      - [record+4]  = height
      - [record+6]  = header_size
      - [record+8]  = format flags, low bits select blitter; 0x0305 means TW4
      - [record+10..] contain offsets/bounds.
      - KE.EXE then sets ESI += header_size and decodes TW4 row command streams.

    This replaces the previous fixed-row and smart heuristics.
    """
    data = decode_file(path).data
    palette = _flat_palette(_palette_for(data_dir))
    if len(data) < 2:
        return [], []

    count = struct.unpack_from("<H", data, 0)[0]
    pos = 2
    sprites: List[Image.Image] = []
    metas: list[dict] = []

    for index in range(count):
        if pos + 30 > len(data):
            break

        record_start = pos
        record_size = struct.unpack_from("<H", data, record_start)[0]
        header = record_start + 2
        record_end = record_start + record_size

        if record_size <= 0 or record_end > len(data) or header + 28 > len(data):
            break

        width, height, header_size, format_word = struct.unpack_from("<HHHH", data, header)
        bounds = struct.unpack_from("<hhhh", data, header + 8)
        offsets = [struct.unpack_from("<H", data, header + 16 + i * 2)[0] for i in range(5)]
        extra = struct.unpack_from("<H", data, header + 26)[0]

        if width <= 0 or height <= 0 or width > 1024 or height > 1024:
            pos = record_end
            continue

        # All observed game BOBs are 0x0305/TW4. Keep a defensive fallback anyway.
        if (format_word & 0x7) == 5:
            im = _decode_tw4_rle_record(data, record_start, width, height, header_size, offsets, record_end, palette)
            decoder = "tw4_rle_exact"
        else:
            im = _decode_tw4_rle_record(data, record_start, width, height, header_size, offsets, record_end, palette)
            decoder = "tw4_rle_exact_assumed"

        sprites.append(im)
        metas.append(
            {
                "index": index,
                "record_start": record_start,
                "record_size": record_size,
                "width": width,
                "height": height,
                "header_size": header_size,
                "format_word": format_word,
                "bounds": bounds,
                "offsets": offsets,
                "extra": extra,
                "decoder": decoder,
            }
        )

        pos = record_end

    return sprites, metas
