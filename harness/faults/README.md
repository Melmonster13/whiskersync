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

To start a fault partway through a test (say, the airline goes down after a quote), call `transport.add_rule(rule)`.

## Gaps found with this harness (fixed)

Both were first pinned in `modules/m4_agent/test_resilience.py` as strict expected failures (`xfail`), then fixed in a later commit.

1. **Non-JSON replies crashed the dispatcher.** A 200 with a broken body, or a 404 with an HTML body, raised a JSON parsing error, so the agent got `internal_error`. **Fix:** any reply that isn't readable JSON now becomes `airline_unavailable`.
2. **A lost write was reported as a failure.** If the confirm was applied but its reply was lost, the booking **had** changed while the agent told the caller it failed. **Fix:** after an unclear confirm (a timeout, a 5xx, or an unreadable reply), the booking is re-read and the caller hears what actually happened. If the re-check fails too, the answer is `rebook_status_unknown`, which tells the agent not to confirm again.

## Run

```bash
.venv/bin/pytest harness/faults modules/m4_agent/test_resilience.py -rxX
```
