# Decisions

Format: `date | choice | why`

- 2026-10-01 | pytest config in `pyproject.toml`, not `pytest.ini` | one file for tool config as the repo grows
- 2026-10-01 | `live` and `evals` markers; CI runs `-m "not live and not evals"` | CI never makes live API calls or spends credits
- 2026-10-01 | m3 resolver: nearest grant up the tree wins, not highest role on the path | lets a child downgrade or deny (`Role.NONE`) what a parent grants
- 2026-10-01 | m3 resolver: on one node, a user grant beats group grants; among groups, highest wins | a user-specific grant is the more deliberate override
