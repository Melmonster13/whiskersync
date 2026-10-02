# m4 — Airline rebooking voice agent

**Problem:** a voice agent that changes real bookings has to be safe before it's clever. It must verify the caller, never change anything without a clear spoken yes, survive a slow or failing backend, leave an audit trail of every action, and be measurable on behaviour and latency. **Approach:** an ElevenLabs agent, defined in code, calls four tools that run in our own process and reach a mock airline over HTTP. Rebooking takes two steps: `quote_rebook` never writes and returns a single-use confirmation id that expires; `confirm_rebook` is the only write and is a dry run unless `DRY_RUN` is explicitly false. One dispatcher checks every call's arguments, runs the tool, turns failures into replies the agent can speak, and writes an audit line. Live evals drive scripted callers through the real agent, then check outcomes with rules and ElevenLabs' built-in grader, and report p50/p95 latency for each stage. **Result:** 96 offline tests pass in CI (51 agent, 12 mock airline, 33 eval harness), including a replayed conversation through the SDK's real tool-call path. **Nothing has run against the live ElevenLabs API yet**, so there are no eval or latency results so far.

## Layout

| Path | What |
|---|---|
| `tools.py` | The four tools, the quote/confirm gate, and dry-run handling |
| `agent.py` | `handle_tool_call()`: checks arguments, runs the tool, writes the audit line |
| `audit.py` | Append-only JSONL audit log |
| `config.py` | System prompt, first message, tool schemas (generated from `TOOL_PARAMS`), and judge criteria |
| `provision.py` | Creates or updates the agent; refuses non-stock voices |
| `session.py` | Live voice or text session; registers tools with the SDK |
| `sandbox/mock_airline/` | FastAPI and SQLite mock airline with synthetic seed data |
| `harness/evals/` | Scenarios, rule-based checks, latency metrics, live runner |
| `harness/replay/` | Hand-written conversation fixtures in the SDK message format |

## Tools

| Tool | Writes? | Notes |
|---|---|---|
| `lookup_booking(confirmation_code, last_name)` | No | Code and name must both match |
| `search_flights(origin, destination, date)` | No | Hides full flights |
| `quote_rebook(confirmation_code, last_name, new_flight_id)` | No | Re-checks the name; same route only; single-use id, 5 min TTL |
| `confirm_rebook(confirmation_id)` | **Yes** | Dry run unless `DRY_RUN=false` |

## Edge cases

**Tools and gate**

| Case | Behaviour | Test |
|---|---|---|
| Wrong last name | `booking_not_found`, the same as an unknown code, so the code's existence isn't revealed | `test_lookup_booking_not_found`, `test_read_booking_not_found` |
| `../` or other non-alphanumeric ids | Rejected before any request | `test_lookup_booking_not_found`, `test_quote_errors` |
| Full flights in search | Hidden | `test_search_flights_hides_full_flights` |
| Quote the same flight, a full flight, another route, or an unknown flight | `same_flight`, `flight_full`, `different_route`, `flight_not_found` | `test_quote_errors` |
| Quote | Never writes | `test_quote_does_not_write` |
| Confirm in dry-run mode | Reports the change, writes nothing | `test_confirm_dry_run_does_not_write` |
| Confirm the same id twice | Second call is `unknown_confirmation`; no double booking | `test_confirm_is_single_use` |
| Confirm at or after the TTL | `confirmation_expired` | `test_confirm_expired` |
| Flight fills up between quote and confirm | `flight_full`; booking unchanged | `test_confirm_flight_filled_after_quote` |
| Failed flight change on the airline side | Seats and booking both unchanged | `test_change_flight_errors_leave_data_unchanged` |
| `DRY_RUN` unset, empty, or anything but false/0/no | Dry run | `test_dry_run_from_env` |

**Dispatcher and audit**

| Case | Behaviour | Test |
|---|---|---|
| Unknown tool name | `unknown_tool`, audited as rejected | `test_unknown_tool_is_rejected` |
| Missing, extra, or wrong-type arguments; not an object | `invalid_arguments`, audited as rejected | `test_invalid_arguments_are_rejected` |
| Airline down or timing out | `airline_unavailable` with a speakable message, audited | `test_airline_unavailable` |
| Every call, whatever its outcome | Exactly one audit line, with conversation id, arguments, outcome and dry-run flag | `test_successful_call_is_audited`, `test_quote_then_confirm_audits_every_call` |

**SDK bridge and config**

| Case | Behaviour | Test |
|---|---|---|
| SDK adds `tool_call_id` to arguments | Stripped before the strict argument check, and left out of the audit log | `test_replay_rebook_conversation`, `test_bridge_returns_errors_as_results` |
| A tool fails | Sent to the agent as an `{ok: false, error, message}` result, not an SDK error | `test_bridge_returns_errors_as_results` |
| Full conversation replayed in dry-run and live mode | Correct replies, audit trail, and booking state | `test_replay_rebook_conversation` |
| Tool schemas drift from the dispatcher | Prevented: schemas are generated from `TOOL_PARAMS` and checked | `test_config_parses_with_sdk_models` |
| Cloned, professional, generated or famous voice | Provisioning refuses before creating anything | `test_provision_refuses_non_stock_voice` |

**Evals**

| Case | Behaviour | Test |
|---|---|---|
| A tool was tried and failed where it must not succeed | Passes | `test_check` |
| A forbidden tool was called, even if rejected | Fails | `test_check` |
| Judge says `unknown` | Doesn't fail | `test_check` |
| Text session, so no speech-to-text timings | Shows `n/a`, not 0 | `test_stage_latencies_text_session_has_no_stt`, `test_summarize_and_table` |
| Unknown timing metric names | Listed so the mapping can be fixed | `test_unmapped_keys_are_reported` |
| Analysis still running, or never finishing | Polls, then `TimeoutError` | `test_wait_for_analysis_polls_until_done`, `test_wait_for_analysis_times_out` |

## Eval scenarios

`happy_path`, `wrong_last_name`, `full_flight`, `user_declines`, `out_of_scope`, `different_route`. Each starts from a fresh in-memory airline and is forced into dry-run mode. They're defined in `harness/evals/scenarios.py`.

## First live run

1. Put `ELEVENLABS_API_KEY` and a stock `ELEVENLABS_VOICE_ID` in `.env`.
2. `make agent`, then copy the printed id into `ELEVENLABS_AGENT_ID`.
3. `make chat` (start `make airline` in another terminal first) for a quick text check.
4. `make evals` (costs credits). Check the "unmapped metric keys" line, then fix `STAGE_METRICS` in `harness/evals/metrics.py`.
5. For speech-to-text latency, use a voice session (`make talk`, which needs `pyaudio`), then `make latency IDS="<conversation id>"`.

## Open questions

- **Metric names:** the stage mapping and the seconds unit are guesses; the SDK doesn't define either.
- **Text-only sessions:** it's unverified whether the voice agent accepts them without extra setup; `make chat` and the evals depend on it.
- **Replay fixtures:** they're hand-written, not recorded. Re-record them after the first live run.
- **SDK upgrades:** the replay test uses a private SDK method (`Conversation._handle_message`), which is why `elevenlabs` is pinned to `~=2.70.0`.
- **Using your own voice:** it's blocked by the stock-voice guard; using it would need an explicit allowlist.

## Trade-offs

See `DECISIONS.md`: tools over HTTP; two-step gate and default dry run; client tools instead of webhooks; agent defined in code; our own eval runner instead of ElevenLabs simulations; text-driven evals; ElevenLabs grader as judge; latency mapping.

## Run

```bash
make test
```
