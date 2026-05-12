from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import shutil
import subprocess


@dataclass(frozen=True)
class LeObject:
    index: int
    size: int
    base: int
    flags: int
    page_map_index: int
    page_count: int
    output_file: str


@dataclass(frozen=True)
class LeSummary:
    exe: str
    le_offset: int
    page_size: int
    page_count: int
    entry_object: int
    entry_offset: int
    stack_object: int
    stack_offset: int
    data_pages_offset: int
    objects: list[LeObject]


def u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little")


def extract_le_objects(exe_path: Path, out_dir: Path, write_disassembly: bool = True) -> LeSummary:
    data = exe_path.read_bytes()
    if data[:2] != b"MZ":
        raise ValueError("Not an MZ executable")

    le_offset = u32(data, 0x3C)
    if data[le_offset : le_offset + 2] != b"LE":
        raise ValueError("MZ does not point to an LE header")

    page_count = u32(data, le_offset + 0x14)
    entry_object = u32(data, le_offset + 0x18)
    entry_offset = u32(data, le_offset + 0x1C)
    stack_object = u32(data, le_offset + 0x20)
    stack_offset = u32(data, le_offset + 0x24)
    page_size = u32(data, le_offset + 0x28)
    obj_table_offset = le_offset + u32(data, le_offset + 0x40)
    obj_count = u32(data, le_offset + 0x44)
    data_pages_offset = u32(data, le_offset + 0x80)

    out_dir.mkdir(parents=True, exist_ok=True)
    objects: list[LeObject] = []

    for index in range(obj_count):
        record = obj_table_offset + index * 24
        size = u32(data, record)
        base = u32(data, record + 4)
        flags = u32(data, record + 8)
        page_map_index = u32(data, record + 12)
        obj_page_count = u32(data, record + 16)

        blob = bytearray()
        for page in range(obj_page_count):
            offset = data_pages_offset + (page_map_index - 1 + page) * page_size
            blob.extend(data[offset : offset + page_size])
        blob = blob[:size]

        name = f"object_{index + 1:02d}_base_{base:05x}.bin"
        output = out_dir / name
        output.write_bytes(blob)
        objects.append(LeObject(index + 1, size, base, flags, page_map_index, obj_page_count, name))

        if write_disassembly and shutil.which("objdump"):
            asm_path = out_dir / name.replace(".bin", ".asm")
            cmd = [
                "objdump",
                "-b",
                "binary",
                "-mi386",
                "-M",
                "intel",
                f"--adjust-vma=0x{base:x}",
                "-D",
                str(output),
            ]
            with asm_path.open("w", encoding="utf-8", errors="replace") as handle:
                subprocess.run(cmd, stdout=handle, stderr=subprocess.STDOUT, check=False)

    summary = LeSummary(
        exe=exe_path.name,
        le_offset=le_offset,
        page_size=page_size,
        page_count=page_count,
        entry_object=entry_object,
        entry_offset=entry_offset,
        stack_object=stack_object,
        stack_offset=stack_offset,
        data_pages_offset=data_pages_offset,
        objects=objects,
    )
    (out_dir / "le_summary.json").write_text(json.dumps(asdict(summary), indent=2), encoding="utf-8")
    return summary
