# Fault injection

`FaultTransport` wraps any `httpx` async transport and injects failures between the m4 agent's tools and the airline. The tools and the airline don't change. Randomness and sleeping are injected, so tests are repeatable and never actually wait.

## Fault kinds

| Kind | What happens | Reaches the airline? |
|---|---|---|
| `latency` | Waits `delay_s` (fixed, or a random value in a `(min, max)` range), then carries on | Yes |
| `status` | Returns `status_code` (default 503) with a plain-text, non-JSON body | No |
| `connect_error` | Raises `httpx.ConnectError` | No |
| `timeout` | Raises `httpx.ReadTimeout` | No |
| `bad_json` | Returns 200 with a truncated JSON body | No |
| `timeout_after_send` | Sends the request, so the change takes effect, then raises `httpx.ReadTimeout` (a lost write) | **Yes** |

Each `FaultRule` can also limit itself by HTTP method, by a path regex (which must match the whole path), by `probability`, and by `times` (fire at most N times, then recover).

Rules apply in order. Latency rules add up and carry on; the first other rule that fires decides the outcome. Every fault that fires is recorded in `transport.log`.

## Profiles

Set `FAULT_PROFILE` in `.env` to run `make chat` / `make talk` against a misbehaving airline:

| Profile | Rules |
|---|---|
| `none` (default) | No faults |
| `slow` | 1–3 s latency on every request |
| `flaky` | 30% chance of 0.5–2 s latency, then a 30% chance of a 503 |
| `down` | Every request fails to connect |
| `lost_write` | The first booking change is applied but its reply is lost |

## Known gaps found with this harness

Both are tested in `modules/m4_agent/test_resilience.py` as strict expected failures (`xfail`), so fixing a gap makes CI fail until its marker is removed.

1. **Non-JSON replies crash the dispatcher.** A 200 with a broken body, or a 404 with an HTML body, raises a JSON parsing error. The agent gets `internal_error` instead of `airline_unavailable`.
2. **A lost write is reported as a failure.** If the confirm request is applied but its reply is lost, the booking **has** changed, the agent tells the caller it failed, and the quote id is already used up. Planned fix: after an unclear confirm, re-check the booking and report what actually happened.

## Run

```bash
.venv/bin/pytest harness/faults modules/m4_agent/test_resilience.py -rxX
```
