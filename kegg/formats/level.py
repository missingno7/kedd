from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

from .cod import decode_file

# Verified from the gameplay screenshot and file sizes:
# KE_LVL.DIG payload: 40 * 275 bytes, where 275 = 18 * 15 + 5.
BRICK_GRID_WIDTH = 18
BRICK_GRID_HEIGHT = 15
BRICK_GRID_SIZE = BRICK_GRID_WIDTH * BRICK_GRID_HEIGHT
VISUAL_LEVEL_HEADER_SIZE = 4
VISUAL_LEVEL_EXTRA_SIZE = 5
VISUAL_LEVEL_RECORD_SIZE = BRICK_GRID_SIZE + VISUAL_LEVEL_EXTRA_SIZE

# Corrected finding:
# KE_LDCWC.TAB payload: 60 * 586 bytes.
#
# Each record:
#   0x000..0x009  10 bytes metadata/header
#   0x00a..0x225  18x15 little-endian word grid = 540 bytes
#   0x226..0x249  36 bytes tail/extra data
#
# The previous 40*879 parsing was wrong because 879 = 1.5 * 586.
LOGIC_LEVEL_HEADER_SIZE = 10
LOGIC_LEVEL_RECORD_SIZE = 586
LOGIC_LEVEL_LAYER_COUNT = 2
LOGIC_LEVEL_TAIL_SIZE = LOGIC_LEVEL_RECORD_SIZE - LOGIC_LEVEL_HEADER_SIZE - BRICK_GRID_SIZE * 2


@dataclass(frozen=True)
class VisualLevel:
    number: int
    cells: bytes
    extra: bytes

    def rows(self) -> List[List[int]]:
        return [
            list(self.cells[y * BRICK_GRID_WIDTH : (y + 1) * BRICK_GRID_WIDTH])
            for y in range(BRICK_GRID_HEIGHT)
        ]


@dataclass(frozen=True)
class LogicLevel:
    number: int
    layers: List[bytes]
    tail: bytes

    def layer_rows(self, layer_index: int) -> List[List[int]]:
        layer = self.layers[layer_index]
        return [
            list(layer[y * BRICK_GRID_WIDTH : (y + 1) * BRICK_GRID_WIDTH])
            for y in range(BRICK_GRID_HEIGHT)
        ]


@dataclass(frozen=True)
class LevelSet:
    visual_header: bytes
    visual_levels: List[VisualLevel]
    logic_levels: List[LogicLevel]

    @property
    def level_count(self) -> int:
        return max(len(self.visual_levels), len(self.logic_levels))


def parse_visual_levels(path: Path) -> tuple[bytes, List[VisualLevel]]:
    data = decode_file(path).data
    if len(data) < VISUAL_LEVEL_HEADER_SIZE:
        raise ValueError(f"{path.name}: too small for KE_LVL.DIG")
    payload = data[VISUAL_LEVEL_HEADER_SIZE:]
    if len(payload) % VISUAL_LEVEL_RECORD_SIZE != 0:
        raise ValueError(
            f"{path.name}: unexpected payload size {len(payload)}; "
            f"expected a multiple of {VISUAL_LEVEL_RECORD_SIZE}"
        )
    levels: List[VisualLevel] = []
    for i in range(len(payload) // VISUAL_LEVEL_RECORD_SIZE):
        start = i * VISUAL_LEVEL_RECORD_SIZE
        record = payload[start : start + VISUAL_LEVEL_RECORD_SIZE]
        levels.append(
            VisualLevel(
                number=i + 1,
                cells=record[:BRICK_GRID_SIZE],
                extra=record[BRICK_GRID_SIZE:],
            )
        )
    return data[:VISUAL_LEVEL_HEADER_SIZE], levels


def parse_logic_levels(path: Path) -> List[LogicLevel]:
    """Parse KE_LDCWC.TAB as 60 records of 586 bytes.

    This is primarily a raw diagnostic view. The gameplay brick renderer uses
    parse_render_levels(), which reads the 18x15 word grid at byte offset 10.
    """
    data = decode_file(path).data
    if len(data) % LOGIC_LEVEL_RECORD_SIZE != 0:
        raise ValueError(
            f"{path.name}: unexpected size {len(data)}; "
            f"expected a multiple of {LOGIC_LEVEL_RECORD_SIZE}"
        )
    levels: List[LogicLevel] = []
    for i in range(len(data) // LOGIC_LEVEL_RECORD_SIZE):
        base = i * LOGIC_LEVEL_RECORD_SIZE
        record = data[base : base + LOGIC_LEVEL_RECORD_SIZE]
        header = record[:LOGIC_LEVEL_HEADER_SIZE]
        grid_bytes = record[LOGIC_LEVEL_HEADER_SIZE : LOGIC_LEVEL_HEADER_SIZE + BRICK_GRID_SIZE * 2]

        # Two diagnostic byte layers: low bytes and high bytes of the render word grid.
        low_bytes = bytes(grid_bytes[j * 2] for j in range(BRICK_GRID_SIZE))
        high_bytes = bytes(grid_bytes[j * 2 + 1] for j in range(BRICK_GRID_SIZE))

        levels.append(
            LogicLevel(
                number=i + 1,
                layers=[low_bytes, high_bytes],
                tail=header,
            )
        )
    return levels


def load_level_set(data_dir: Path) -> LevelSet:
    visual_header, visual_levels = parse_visual_levels(data_dir / "KE_LVL.DIG")
    logic_levels = parse_logic_levels(data_dir / "KE_LDCWC.TAB")
    return LevelSet(visual_header=visual_header, visual_levels=visual_levels, logic_levels=logic_levels)


def format_grid(rows: Sequence[Sequence[int]]) -> str:
    return "\n".join(" ".join(f"{value:02x}" for value in row) for row in rows)

# KE_LDCWC.TAB record structure:
#   0x000..0x009  10 bytes per-level metadata/header
#   0x00a..0x225  18x15 little-endian word grid
#   0x226..0x249  36 bytes tail/extra data
#
# Each grid entry is a little-endian word:
#   high byte = 1-based visible KE_BRICK.BOB sprite id
#   low byte  = per-cell gameplay metadata / KE_SPELL.BOB powerup id
RENDER_WORD_GRID_OFFSET = LOGIC_LEVEL_HEADER_SIZE
RENDER_WORD_GRID_SIZE_BYTES = BRICK_GRID_SIZE * 2

# Gameplay powerups / spell sprites.
#
# Confirmed from KE.EXE:
#   - the level cell low byte is not a direct KE_SPELL.BOB frame id.
#   - when a brick is destroyed, the game does roughly:
#
#       if brick_code in 0x31..0x60 and (low_byte & 0xFC) != 0:
#           drop_type = (low_byte >> 2) - 1
#           drop_variant = low_byte & 0x03
#           spawn_drop(drop_type, drop_variant)
#
#   - drop_type indexes a table at DS:0x60F0.
#   - each table entry points to an animation sequence of KE_SPELL.BOB frames.
#   - sorting the 50 unique sprite pointers from those animation sequences maps
#     exactly to KE_SPELL.BOB frames 24..73.
POWERUP_SPELL_ID_MIN = 24
POWERUP_SPELL_ID_MAX = 73

SPELL_RANGES: list[tuple[int, int, str]] = [
    (24, 24, "Darkness"),
    (25, 25, "Protection"),
    (26, 26, "Random spell"),
    (27, 27, "Extra life"),
    (28, 29, "Super ball"),
    (30, 30, "Dum ball"),
    (31, 31, "Cage"),
    (32, 32, "Straight shot"),
    (33, 33, "Fast straight shot"),
    (34, 34, "Wide shot"),
    (35, 35, "Fast wide shot"),
    (36, 36, "Plasma blast"),
    (37, 37, "Fast plasma blast"),
    (38, 38, "Extra ball"),
    (39, 39, "Pontoon"),
    (40, 42, "Drunk"),
    (43, 43, "Score X2"),
    (44, 45, "Jetpack"),
    (46, 46, "AI racket"),
    (47, 51, "Grow ball"),
    (52, 56, "Grow racket"),
    (57, 57, "Knife"),
    (58, 58, "Slow ball"),
    (59, 59, "Fast ball"),
    (60, 60, "Glue"),
    (61, 65, "Shrink racket"),
    (66, 70, "Shrink ball"),
    (71, 73, "Unknown spell 71-73"),
]

# EXE drop_type -> visual KE_SPELL.BOB animation frames.
# Derived from the table at DS:0x60F0.
SPELL_DROP_TYPE_TO_FRAMES: dict[int, list[int]] = {
    0: [52, 53, 54, 55, 56, 55, 54, 53],  # Grow racket
    1: [57],                              # Knife
    2: [43],                              # Score X2
    3: [40, 41, 42],                      # Drunk
    4: [66, 67, 68, 69, 70, 69, 68, 67],  # Shrink ball
    5: [60],                              # Glue
    6: [27],                              # Extra life
    7: [38],                              # Extra ball
    8: [47, 48, 49, 50, 51, 50, 49, 48],  # Grow ball
    9: [24],                              # Darkness
    10: [59],                             # Fast ball
    11: [58],                             # Slow ball
    12: [46],                             # AI racket
    13: [44, 45],                         # Jetpack
    14: [31],                             # Cage
    15: [25],                             # Protection
    16: [36],                             # Plasma blast
    17: [28, 29],                         # Super ball
    18: [30],                             # Dum ball
    19: [39],                             # Pontoon
    20: [37],                             # Fast plasma blast
    21: [26],                             # Random spell
    22: [61, 62, 63, 64, 65, 64, 63, 62], # Shrink racket
    23: [32],                             # Straight shot
    24: [34],                             # Wide shot
    25: [33],                             # Fast straight shot
    26: [35],                             # Fast wide shot
    27: [71, 72, 73],                     # Unknown spell 71-73
}


def spell_name_for_frame(value: int) -> str | None:
    """Return the logical spell represented by a KE_SPELL.BOB visual frame."""
    for start, end, name in SPELL_RANGES:
        if start <= value <= end:
            return name
    return None


def spell_drop_type_for_code(value: int) -> int | None:
    """Return EXE drop_type from a level-cell low byte.

    The lower two bits are a variant/channel; the upper six bits encode the
    drop type as (low_byte >> 2) - 1.
    """
    upper = value >> 2
    if upper == 0:
        return None
    drop_type = upper - 1
    if drop_type not in SPELL_DROP_TYPE_TO_FRAMES:
        return None
    return drop_type


def spell_variant_for_code(value: int) -> int:
    return value & 0x03


def spell_frames_for_code(value: int) -> list[int] | None:
    drop_type = spell_drop_type_for_code(value)
    if drop_type is None:
        return None
    return SPELL_DROP_TYPE_TO_FRAMES[drop_type]


def representative_spell_frame_for_code(value: int) -> int | None:
    frames = spell_frames_for_code(value)
    return frames[0] if frames else None


def spell_bob_sprite_index_for_frame(frame: int) -> int:
    """Convert game/atlas spell frame id to actual KE_SPELL.BOB record index.

    KE.EXE's animation table points at records 34..83, while the gameplay spell
    numbering used in notes/atlas is 24..73. The difference is +10.

    Example:
      Darkness frame 24 -> KE_SPELL.BOB record 34
      Grow racket frame 52 -> KE_SPELL.BOB record 62
    """
    return frame + 10


def representative_spell_bob_sprite_index_for_code(value: int) -> int | None:
    frame = representative_spell_frame_for_code(value)
    return spell_bob_sprite_index_for_frame(frame) if frame is not None else None


def spell_name_for_code(value: int) -> str | None:
    frame = representative_spell_frame_for_code(value)
    if frame is None:
        return None
    return spell_name_for_frame(frame)


def spell_name_for_id(value: int) -> str | None:
    """Backward-compatible alias for the level-cell metadata/drop code mapping."""
    return spell_name_for_code(value)


def is_powerup_spell_id(value: int) -> bool:
    return spell_drop_type_for_code(value) is not None


@dataclass(frozen=True)
class RenderCell:
    x: int
    y: int
    raw_word: int

    @property
    def brick_id(self) -> int:
        """Stored brick id from the level data high byte.

        The original level data uses 1-based brick ids for visible bricks.
        0 means empty/no brick.
        """
        return (self.raw_word >> 8) & 0xFF

    @property
    def brick_sprite_id(self) -> int | None:
        """Zero-based KE_BRICK.BOB sprite index used for rendering."""
        return self.brick_id - 1 if self.brick_id > 0 else None

    @property
    def brick_class(self) -> str:
        """Human-readable brick category based on rendered KE_BRICK.BOB index."""
        sid = self.brick_sprite_id
        if sid is None:
            return "empty"
        if 0 <= sid <= 47 or 96 <= sid <= 143:
            return "normal breakable"
        if 48 <= sid <= 95:
            return "breakable with powerup marker"
        if 144 <= sid <= 246:
            return "unbreakable"
        if sid in (247, 248):
            return "portal"
        if 249 <= sid <= 255:
            return "respawning"
        return "unknown/special"

    @property
    def can_contain_powerup(self) -> bool:
        # Observed in game levels: only the dotted breakable bricks in 48..95
        # carry hidden powerups. The brick id does not itself determine the
        # spell, but it is a useful validation/debug rule.
        sid = self.brick_sprite_id
        return sid is not None and 48 <= sid <= 95

    @property
    def flags(self) -> int:
        return self.raw_word & 0xFF

    @property
    def powerup_code(self) -> int | None:
        """Return level-cell low byte if it encodes a known drop."""
        return self.flags if is_powerup_spell_id(self.flags) else None

    @property
    def powerup_drop_type(self) -> int | None:
        """Return EXE drop_type = (low_byte >> 2) - 1."""
        return spell_drop_type_for_code(self.flags)

    @property
    def powerup_variant(self) -> int | None:
        """Return low-byte variant/channel bits for a known drop."""
        return spell_variant_for_code(self.flags) if self.powerup_drop_type is not None else None

    @property
    def powerup_frames(self) -> list[int] | None:
        """Return KE_SPELL.BOB animation frames for this drop."""
        return spell_frames_for_code(self.flags)

    @property
    def powerup_spell_id(self) -> int | None:
        """Return representative gameplay spell frame id, e.g. 24 for Darkness."""
        return representative_spell_frame_for_code(self.flags)

    @property
    def powerup_spell_bob_sprite_index(self) -> int | None:
        """Return actual zero-based KE_SPELL.BOB record index used for drawing."""
        return representative_spell_bob_sprite_index_for_code(self.flags)

    @property
    def powerup_spell_name(self) -> str | None:
        return spell_name_for_code(self.flags)


@dataclass(frozen=True)
class RenderLevel:
    number: int
    source_record: int
    cells: List[RenderCell]

    def raw_words(self) -> List[int]:
        return [cell.raw_word for cell in self.cells]

    def brick_ids(self) -> List[int]:
        return [cell.brick_id for cell in self.cells]

    def flags(self) -> List[int]:
        return [cell.flags for cell in self.cells]


def parse_render_levels(path: Path) -> List[RenderLevel]:
    """Parse the best-current renderable 18x15 brick grids from KE_LDCWC.TAB.

    This is still marked experimental because the game's exact level ordering
    and the meaning of the low byte are not fully solved. However, this view is
    the first one that visually matches captured gameplay levels, including the
    pyramid-shaped level shown in the level 03 screenshot.
    """
    data = decode_file(path).data
    if len(data) % LOGIC_LEVEL_RECORD_SIZE != 0:
        raise ValueError(f"{path.name}: unexpected size {len(data)}")
    levels: List[RenderLevel] = []
    record_count = len(data) // LOGIC_LEVEL_RECORD_SIZE
    for record_index in range(record_count):
        base = record_index * LOGIC_LEVEL_RECORD_SIZE + RENDER_WORD_GRID_OFFSET
        if base + RENDER_WORD_GRID_SIZE_BYTES > len(data):
            continue
        cells: List[RenderCell] = []
        for i in range(BRICK_GRID_SIZE):
            raw = int.from_bytes(data[base + i * 2 : base + i * 2 + 2], "little")
            cells.append(RenderCell(x=i % BRICK_GRID_WIDTH, y=i // BRICK_GRID_WIDTH, raw_word=raw))
        levels.append(RenderLevel(number=record_index + 1, source_record=record_index + 1, cells=cells))
    return levels
