from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from .cod import decode_file


BACKGROUND_FILL_FIRST = 6
BACKGROUND_FILL_LAST = 46
BACKGROUND_SLOT_COUNT = BACKGROUND_FILL_LAST - BACKGROUND_FILL_FIRST + 1
TABLE_ENTRY_SIZE = 8
TABLE_SIZE = BACKGROUND_SLOT_COUNT * TABLE_ENTRY_SIZE


def _bob_record_starts(path: Path) -> list[int]:
    data = decode_file(path).data
    if len(data) < 2:
        raise ValueError(f"{path.name}: too small for BOB")
    count = int.from_bytes(data[0:2], "little")
    starts: list[int] = []
    pos = 2
    for _ in range(count):
        if pos + 2 > len(data):
            raise ValueError(f"{path.name}: truncated BOB record table")
        size = int.from_bytes(data[pos : pos + 2], "little")
        if size <= 0 or pos + size > len(data):
            raise ValueError(f"{path.name}: invalid BOB record size at {pos}")
        starts.append(pos)
        pos += size
    return starts


@dataclass
class BackgroundTableStore:
    exe_path: Path
    table_offset: int
    fill_sprite_starts: dict[int, int]
    mapping: list[int]
    modified: bool = False

    @classmethod
    def load(cls, exe_path: Path, fill_bob_path: Path) -> "BackgroundTableStore":
        exe_data = exe_path.read_bytes()
        starts = _bob_record_starts(fill_bob_path)
        fill_sprite_starts = {
            sprite_id: starts[sprite_id]
            for sprite_id in range(BACKGROUND_FILL_FIRST, BACKGROUND_FILL_LAST + 1)
            if sprite_id < len(starts)
        }
        if len(fill_sprite_starts) != BACKGROUND_SLOT_COUNT:
            raise ValueError("KE_FILL.BOB does not contain the expected background sprite range 6..46")

        candidate_offsets: list[int] = []
        allowed_offsets = set(fill_sprite_starts.values())
        for off in range(0, max(0, len(exe_data) - TABLE_SIZE + 1)):
            ok = True
            for slot in range(BACKGROUND_SLOT_COUNT):
                pos = off + slot * TABLE_ENTRY_SIZE
                ptr = int.from_bytes(exe_data[pos : pos + 4], "little")
                zero = int.from_bytes(exe_data[pos + 4 : pos + 8], "little")
                if ptr not in allowed_offsets or zero != 0:
                    ok = False
                    break
            if ok:
                candidate_offsets.append(off)

        if not candidate_offsets:
            raise ValueError("Could not find the KE_FILL background pointer table in KE.EXE")
        if len(candidate_offsets) > 1:
            # Prefer the exact vanilla sequence if it exists.
            vanilla = bytes().join(
                fill_sprite_starts[sprite_id].to_bytes(4, "little") + (0).to_bytes(4, "little")
                for sprite_id in range(BACKGROUND_FILL_FIRST, BACKGROUND_FILL_LAST + 1)
            )
            exact = exe_data.find(vanilla)
            table_offset = exact if exact >= 0 else candidate_offsets[0]
        else:
            table_offset = candidate_offsets[0]

        start_to_sprite = {start: sprite_id for sprite_id, start in fill_sprite_starts.items()}
        mapping: list[int] = []
        for slot in range(BACKGROUND_SLOT_COUNT):
            pos = table_offset + slot * TABLE_ENTRY_SIZE
            ptr = int.from_bytes(exe_data[pos : pos + 4], "little")
            mapping.append(start_to_sprite[ptr])

        return cls(
            exe_path=exe_path,
            table_offset=table_offset,
            fill_sprite_starts=fill_sprite_starts,
            mapping=mapping,
        )

    @property
    def slot_count(self) -> int:
        return len(self.mapping)

    def slot_for_level(self, level_number: int) -> int:
        return (max(1, level_number) - 1) % self.slot_count

    def get_fill_sprite_for_level(self, level_number: int) -> int:
        return self.mapping[self.slot_for_level(level_number)]

    def set_fill_sprite_for_level(self, level_number: int, fill_sprite_id: int) -> None:
        if fill_sprite_id not in self.fill_sprite_starts:
            raise ValueError(f"background KE_FILL sprite out of range: {fill_sprite_id}")
        slot = self.slot_for_level(level_number)
        if self.mapping[slot] != fill_sprite_id:
            self.mapping[slot] = fill_sprite_id
            self.modified = True

    def save(self, make_backup: bool = True) -> None:
        data = bytearray(self.exe_path.read_bytes())
        if make_backup:
            backup = self.exe_path.with_suffix(self.exe_path.suffix + ".bak")
            if not backup.exists():
                backup.write_bytes(bytes(data))
        for slot, sprite_id in enumerate(self.mapping):
            pos = self.table_offset + slot * TABLE_ENTRY_SIZE
            ptr = self.fill_sprite_starts[sprite_id]
            data[pos : pos + 4] = ptr.to_bytes(4, "little")
            data[pos + 4 : pos + 8] = (0).to_bytes(4, "little")
        self.exe_path.write_bytes(bytes(data))
        self.modified = False
