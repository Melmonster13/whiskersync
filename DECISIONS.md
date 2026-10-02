# Decisions

Format: `date | choice | why`

- 2026-10-01 | pytest config in `pyproject.toml`, not `pytest.ini` | one file for tool config as the repo grows
- 2026-10-01 | `live` and `evals` markers; CI runs `-m "not live and not evals"` | CI never makes live API calls or spends credits
