# Decisions

Format: `date | choice | why`

- 2026-10-01 | pytest config in `pyproject.toml`, not `pytest.ini` | one file for tool config as the repo grows
- 2026-10-01 | `live` and `evals` markers; CI runs `-m "not live and not evals"` | CI never makes live API calls or spends credits
- 2026-10-01 | m3 resolver: nearest grant up the tree wins, not highest role on the path | lets a child downgrade or deny (`Role.NONE`) what a parent grants
- 2026-10-01 | m3 resolver: on one node, a user grant beats group grants; among groups, highest wins | a user-specific grant is the more deliberate override
- 2026-10-01 | m1 sync: words are active on `[start, end)` | at a shared boundary the next word wins, so there's never a frame with two active words
- 2026-10-01 | m1 sync: in gaps, no active word but the last speaker holds until the next word | avoids speaker label flicker during pauses
- 2026-10-01 | m1 sync: overlapping words allowed; most recently started word still in progress wins | real diarized speech has crosstalk; lookup walks back from the bisect index with a prefix "latest end" to stop early
