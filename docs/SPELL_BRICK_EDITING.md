# Spell-compatible brick editing

Confirmed gameplay/editor rule:

- Spell drops can appear only on the dotted spell brick variants `48..95`.
- Brick `48` is the spell-marked version of brick `0`.
- Therefore the conversion is:

```text
non-spell 0..47  -> spell-marked 48..95   (+48)
spell-marked 48..95 -> non-spell 0..47    (-48)
```

## Editor behavior

The **Bricks** tab intentionally shows:
- `0..47`
- `96+`

It does **not** expose `48..95` directly.

The **Spells** tab enforces the rule:
- placing a spell on brick `0..47` automatically converts it to `+48`
- placing a spell on existing `48..95` changes only the hidden drop metadata
- placing a spell on empty cells, `96+`, unbreakable bricks, portals, or respawning bricks is rejected
- removing a spell from `48..95` converts the brick back to `-48`

The **Bricks** tool preserves hidden spell metadata only when switching a spell-bearing cell to another compatible base brick `0..47`:
- `brick 53` with a spell, switched to base brick `12`, becomes spell variant `60`
- the spell drop type is preserved

If the newly selected brick does **not** support spells (`96+`), hidden spell metadata is cleared.
