# WhiskerSync

[![tests](https://github.com/Melmonster13/whiskersync/actions/workflows/tests.yml/badge.svg)](https://github.com/Melmonster13/whiskersync/actions/workflows/tests.yml)

Four building blocks of a voice-AI product, each built and tested as a standalone module: syncing a transcript to playback, orchestrating multi-language dubbing, resolving hierarchical permissions, and a voice agent that safely changes airline bookings. Built with Python, FastAPI, SQLite and the ElevenLabs Python SDK.

## Modules

| Module | What it does | Tests |
|---|---|---|
| [m1 — Transcript sync](modules/m1_transcript/README.md) | Finds the active word and speaker at any playback time, using `bisect`; handles pauses, crosstalk and ElevenLabs speech-to-text output | 37 |
| [m2 — Dubbing state machine](modules/m2_dubbing/README.md) | One explicit state machine per language task; retries resume the stage that failed; one combined status per job | 54 |
| [m3 — Permissions](modules/m3_permissions/README.md) | Permissions inherited down a resource tree, with overrides and explicit deny; the nearest grant wins | 26 |
| [m4 — Rebooking voice agent](modules/m4_agent/README.md) | An ElevenLabs agent with a gated quote → confirm flow, dry-run by default, an audit log, a mock airline, and live evals with p50/p95 latency per stage | 96 |

Each module README has a problem → approach → result summary, its rules, and a table of edge cases with the test that covers each one.

## Safety by design

- **Every write needs explicit confirmation.** The agent can only change a booking with a single-use, expiring quote id, and every change is a dry run unless `DRY_RUN=false`.
- **Every tool call is audited**, including rejected and failed calls.
- **Synthetic data only.** The mock airline's seed data is made up.
- **Stock voices only.** Agent provisioning refuses cloned and other non-stock voices.
- **No live API calls in CI.** Tests use in-process fakes and replay fixtures; live evals run only on demand.
- **Secrets stay in `.env`**, which is gitignored; `.env.example` has variable names only.

## Quickstart

```bash
make install
```
```bash
make test
```

`make test` runs the full offline suite (213 tests); CI runs the same command on Python 3.12.

Live agent (needs an ElevenLabs API key in `.env`; see the [m4 README](modules/m4_agent/README.md#first-live-run)):

| Command | What |
|---|---|
| `make airline` | Start the mock airline API on port 8000 |
| `make agent` | Create or update the agent from code |
| `make chat` / `make talk` | Text or voice session with the agent |
| `make evals` | Run the six live eval scenarios (costs credits) |
| `make latency IDS="..."` | p50/p95 latency per stage for existing conversations |

## Layout

```
modules/                m1–m4, each with its code, tests, and README
sandbox/mock_airline/   FastAPI + SQLite mock airline (synthetic data)
harness/replay/         conversation fixtures in the SDK message format
harness/evals/          eval scenarios, rule checks, latency metrics, live runner
DECISIONS.md            every non-obvious choice: date, choice, why
```

## Status

m1–m3 are complete. m4 is fully tested offline, but **hasn't run against the live ElevenLabs API yet**, so there are no eval or latency results so far. The [m4 README](modules/m4_agent/README.md#open-questions) lists what the first live run needs to confirm.

## Decisions

The trade-offs behind each module are recorded one line each in [DECISIONS.md](DECISIONS.md).
