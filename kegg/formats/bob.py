from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json

from .cod import decode_file


@dataclass(frozen=True)
class BobHeader:
    file_name: str
    object_count: int
    second_word: int
    width: int
    height: int
    header_size: int
    format_word: int
    bounds_left: int
    bounds_top: int
    bounds_right: int
    bounds_bottom: int
    decoded_size: int
    notes: str


def s16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little", signed=True)


def u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little", signed=False)


def parse_bob_header(path: Path) -> BobHeader:
    decoded = decode_file(path)
    data = decoded.data
    if len(data) < 20:
        raise ValueError(f"{path.name}: too small for a BOB header")

    return BobHeader(
        file_name=path.name,
        object_count=u16(data, 0),
        second_word=u16(data, 2),
        width=u16(data, 4),
        height=u16(data, 6),
        header_size=u16(data, 8),
        format_word=u16(data, 10),
        bounds_left=s16(data, 12),
        bounds_top=s16(data, 14),
        bounds_right=s16(data, 16),
        bounds_bottom=s16(data, 18),
        decoded_size=len(data),
        notes="Header field meanings are partly inferred. Pixel/RLE decoding is not solved yet.",
    )


def dump_bob_analysis(data_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in sorted(data_dir.glob("*.BOB")):
        header = parse_bob_header(path)
        rows.append(asdict(header))
        decoded = decode_file(path).data
        (out_dir / f"{path.stem}.decoded.bin").write_bytes(decoded)

    (out_dir / "bob_headers.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
