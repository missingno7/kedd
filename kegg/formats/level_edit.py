from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

from .cod import decode_file, encode_cod2
from .level import (
    BRICK_GRID_HEIGHT,
    BRICK_GRID_SIZE,
    BRICK_GRID_WIDTH,
    LOGIC_LEVEL_HEADER_SIZE,
    LOGIC_LEVEL_RECORD_SIZE,
    RenderCell,
    RenderLevel,
)


@dataclass
class EditableLevelStore:
    path: Path
    decoded: bytearray
    key_seed_word: int
    modified: bool = False

    @classmethod
    def load(cls, path: Path) -> "EditableLevelStore":
        decoded = decode_file(path)
        if decoded.codec != "COD2" or decoded.key_seed_word is None:
            raise ValueError(f"{path.name}: expected COD2-wrapped level table")
        if len(decoded.data) % LOGIC_LEVEL_RECORD_SIZE != 0:
            raise ValueError(f"{path.name}: unexpected decoded size {len(decoded.data)}")
        return cls(path=path, decoded=bytearray(decoded.data), key_seed_word=decoded.key_seed_word)

    @property
    def level_count(self) -> int:
        return len(self.decoded) // LOGIC_LEVEL_RECORD_SIZE

    def _word_offset(self, level_number: int, x: int, y: int) -> int:
        if not (1 <= level_number <= self.level_count):
            raise IndexError(f"level out of range: {level_number}")
        if not (0 <= x < BRICK_GRID_WIDTH and 0 <= y < BRICK_GRID_HEIGHT):
            raise IndexError(f"cell out of range: {x}, {y}")
        cell_index = y * BRICK_GRID_WIDTH + x
        return (
            (level_number - 1) * LOGIC_LEVEL_RECORD_SIZE
            + LOGIC_LEVEL_HEADER_SIZE
            + cell_index * 2
        )

    def get_word(self, level_number: int, x: int, y: int) -> int:
        off = self._word_offset(level_number, x, y)
        return int.from_bytes(self.decoded[off : off + 2], "little")

    def set_word(self, level_number: int, x: int, y: int, raw_word: int) -> None:
        off = self._word_offset(level_number, x, y)
        raw_word &= 0xFFFF
        before = int.from_bytes(self.decoded[off : off + 2], "little")
        if before != raw_word:
            self.decoded[off : off + 2] = raw_word.to_bytes(2, "little")
            self.modified = True

    def get_cell(self, level_number: int, x: int, y: int) -> RenderCell:
        return RenderCell(x=x, y=y, raw_word=self.get_word(level_number, x, y))

    def render_level(self, level_number: int) -> RenderLevel:
        cells: List[RenderCell] = []
        for i in range(BRICK_GRID_SIZE):
            x = i % BRICK_GRID_WIDTH
            y = i // BRICK_GRID_WIDTH
            cells.append(self.get_cell(level_number, x, y))
        return RenderLevel(number=level_number, source_record=level_number, cells=cells)

    @staticmethod
    def _is_non_spell_breakable_sprite(sprite_id: int | None) -> bool:
        return sprite_id is not None and 0 <= sprite_id <= 47

    @staticmethod
    def _is_spell_variant_sprite(sprite_id: int | None) -> bool:
        return sprite_id is not None and 48 <= sprite_id <= 95

    def set_brick_sprite_id(self, level_number: int, x: int, y: int, sprite_id: int | None) -> None:
        """Place a brick selected from the editor's non-spell brick palette.

        The editor intentionally does not expose sprite ids 48..95 directly:
        those are the spell-marked variants of brick ids 0..47.

        If the edited cell already has a hidden spell drop and the newly chosen
        brick is a spell-compatible base brick 0..47, the editor preserves the
        drop metadata and stores the corresponding dotted +48 variant.

        If the newly chosen brick does not support spells (96+), any existing
        hidden spell metadata is cleared.
        """
        if sprite_id is None:
            self.set_word(level_number, x, y, 0)
            return
        if not (0 <= sprite_id <= 255):
            raise ValueError(f"brick sprite id out of range: {sprite_id}")
        if 48 <= sprite_id <= 95:
            raise ValueError(
                f"brick sprite id {sprite_id} is a spell-marked variant and "
                "must be created by assigning a spell to its base brick"
            )

        current_cell = self.get_cell(level_number, x, y)
        existing_spell_low = current_cell.flags if current_cell.powerup_code is not None else 0

        if self._is_non_spell_breakable_sprite(sprite_id) and existing_spell_low:
            # Preserve the existing hidden spell and convert the newly selected
            # base brick to its dotted spell-marked +48 variant.
            stored_sprite_id = sprite_id + 48
            low = existing_spell_low
        else:
            # Either the target brick is 96+ / otherwise non-spell-capable, or
            # there was no existing spell to preserve.
            stored_sprite_id = sprite_id
            low = 0

        stored_id = stored_sprite_id + 1
        if stored_id > 255:
            raise ValueError(f"brick sprite id cannot be stored as 1-based byte: {stored_sprite_id}")
        self.set_word(level_number, x, y, (stored_id << 8) | low)

    def set_spell_drop_type(self, level_number: int, x: int, y: int, drop_type: int | None) -> bool:
        """Assign a spell drop to a compatible brick.

        Spell drops are legal only on the dotted spell variants 48..95. The
        editor therefore auto-converts a base breakable brick 0..47 to its
        +48 spell-marked variant when assigning a drop. Other brick families
        (empty, 96+, unbreakable, portals, respawning) reject spell assignment.
        """
        if drop_type is None:
            self.erase_spell(level_number, x, y)
            return True
        if not (0 <= drop_type <= 27):
            raise ValueError(f"drop type out of range: {drop_type}")

        cell = self.get_cell(level_number, x, y)
        sprite_id = cell.brick_sprite_id
        if self._is_non_spell_breakable_sprite(sprite_id):
            spell_sprite_id = sprite_id + 48
            stored_id = spell_sprite_id + 1
        elif self._is_spell_variant_sprite(sprite_id):
            stored_id = sprite_id + 1
        else:
            return False

        current_low = cell.flags
        # Preserve existing variant bits if there is already a drop code;
        # otherwise use the common default variant 0.
        existing_upper = current_low >> 2
        variant = current_low & 0x03 if existing_upper != 0 else 0
        low = ((drop_type + 1) << 2) | variant
        self.set_word(level_number, x, y, (stored_id << 8) | low)
        return True

    def erase_brick(self, level_number: int, x: int, y: int) -> None:
        self.set_word(level_number, x, y, 0)

    def erase_spell(self, level_number: int, x: int, y: int) -> None:
        current = self.get_word(level_number, x, y)
        cell = self.get_cell(level_number, x, y)
        sprite_id = cell.brick_sprite_id
        if self._is_spell_variant_sprite(sprite_id):
            # Removing the spell converts 48..95 back to their base 0..47 variants.
            base_sprite_id = sprite_id - 48
            stored_id = base_sprite_id + 1
            self.set_word(level_number, x, y, stored_id << 8)
        else:
            self.set_word(level_number, x, y, current & 0xFF00)

    def clear_level(self, level_number: int) -> None:
        """Clear the full 18x15 brick/spell grid for one level."""
        for y in range(BRICK_GRID_HEIGHT):
            for x in range(BRICK_GRID_WIDTH):
                self.set_word(level_number, x, y, 0)

    def _record_offset(self, level_number: int) -> int:
        if not (1 <= level_number <= self.level_count):
            raise IndexError(f"level out of range: {level_number}")
        return (level_number - 1) * LOGIC_LEVEL_RECORD_SIZE

    def get_spawn_interval(self, level_number: int) -> int:
        """Return the first level-header word.

        KE.EXE loads this into ds:0xddb0 and uses it as a countdown value for
        enemy spawning. The exact unit is still being verified, so the GUI
        labels it as a raw/inferred spawn timer.
        """
        off = self._record_offset(level_number)
        return int.from_bytes(self.decoded[off : off + 2], "little")

    def set_spawn_interval(self, level_number: int, value: int) -> None:
        if not (0 <= value <= 0xFFFF):
            raise ValueError(f"spawn interval out of range: {value}")
        off = self._record_offset(level_number)
        before = int.from_bytes(self.decoded[off : off + 2], "little")
        if before != value:
            self.decoded[off : off + 2] = value.to_bytes(2, "little")
            self.modified = True

    def get_enemy_sequence(self, level_number: int) -> list[int]:
        """Return the 8 raw enemy type bytes at record+2..+9."""
        off = self._record_offset(level_number) + 2
        return list(self.decoded[off : off + 8])

    def set_enemy_sequence_value(self, level_number: int, slot: int, value: int) -> None:
        if not (0 <= slot < 8):
            raise IndexError(f"enemy sequence slot out of range: {slot}")
        if not (0 <= value <= 0xFF):
            raise ValueError(f"enemy sequence value out of range: {value}")
        off = self._record_offset(level_number) + 2 + slot
        if self.decoded[off] != value:
            self.decoded[off] = value
            self.modified = True

    def save(self, make_backup: bool = True) -> None:
        if make_backup:
            backup = self.path.with_suffix(self.path.suffix + ".bak")
            if not backup.exists():
                backup.write_bytes(self.path.read_bytes())
        self.path.write_bytes(encode_cod2(bytes(self.decoded), self.key_seed_word))
        self.modified = False
