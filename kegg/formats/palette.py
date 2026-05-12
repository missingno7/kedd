from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from .cod import decode_file

RGB = Tuple[int, int, int]


def load_vga_palette(path: Path) -> List[RGB]:
    """Load a best-effort 256 color VGA palette.

    Krypton Egg's KE_ALL.PAL is still not fully documented. For editor previews we
    use the first 768 bytes as 256 RGB triples. Values appear to be VGA DAC
    0..63, so they are scaled to 0..255.
    """
    data = decode_file(path).data
    if len(data) < 768:
        raise ValueError(f"{path.name}: not enough bytes for a 256 color palette")
    result: List[RGB] = []
    for i in range(0, 768, 3):
        r, g, b = data[i], data[i + 1], data[i + 2]
        if max(r, g, b) <= 63:
            r, g, b = r * 4, g * 4, b * 4
        result.append((min(r, 255), min(g, 255), min(b, 255)))
    return result


def default_palette() -> List[RGB]:
    """Fallback debug palette: grayscale ramp."""
    return [(i, i, i) for i in range(256)]
