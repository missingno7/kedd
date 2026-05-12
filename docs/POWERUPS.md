# Powerups in level data

Current working interpretation:

- `KE_SPELL.BOB` entries `24..73` are powerups / falling bonus frames.
- The renderable level grid is in `KE_LDCWC.TAB`.
- Each 18x15 cell is currently parsed as a little-endian word:
  - high byte = `KE_BRICK.BOB` sprite id
  - low byte = per-cell metadata
- When the low byte is in `24..73`, it is interpreted as a direct `KE_SPELL.BOB` sprite id for a powerup/drop frame.

This means the first implementation is intentionally direct:

```text
powerup_spell_id = cell_low_byte if 24 <= cell_low_byte <= 73 else None
```

Caveat:

Some `KE_SPELL.BOB` powerups have multiple animation frames, so later we may want a lookup table that maps frame ids to higher-level powerup types, for example:

```text
spell frame 48,49,50,51 -> same logical powerup animation
```

Useful commands:

```bash
python -m kegg.cli analyze-powerups --data-dir game_data
python -m kegg.cli export-powerups --data-dir game_data --out output/powerups
python -m kegg.cli export-powerups --data-dir game_data --out output/powerups --level 3
```
