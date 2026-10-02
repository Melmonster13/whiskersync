# m4 — Airline rebooking voice agent

**Problem:** a voice agent that changes real bookings has to be safe before it's clever. It must verify the caller, never change anything without a clear spoken yes, survive a slow or failing backend, leave an audit trail of every action, and be measurable on behaviour and latency. **Approach:** an ElevenLabs agent, defined in code, calls four tools that run in our own process and reach a mock airline over HTTP. Rebooking takes two steps: `quote_rebook` never writes and returns a single-use confirmation id that expires; `confirm_rebook` is the only write and is a dry run unless `DRY_RUN` is explicitly false. It sends the confirmation id as an idempotency key, so a retry can never apply twice. One dispatcher checks every call's arguments, runs the tool, turns failures into replies the agent can speak, and writes an audit line. Live evals drive scripted callers through the real agent, then check outcomes with rules and ElevenLabs' built-in grader, and report p50/p95 latency for each stage. **Result:** 191 offline tests pass in CI (84 agent, 16 mock airline, 53 eval harness, 38 fault harness), including a replayed conversation through the SDK's real tool-call path and a recorded live conversation. Fault injection found two gaps, pinned them as failing tests, and both are now fixed (see [Resilience](#resilience)). Live, it completed a full dry-run rebooking by chat, and all six eval scenarios pass the rule checks and the ElevenLabs judge (see [Live results](#live-results)).

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
| Text session, so no speech-to-text timings | Shows `n/a`, not 0 | `test_recorded_stages`, `test_recorded_summary_and_table` |
| Tool-call turns also report LLM time | Counted as `llm_tool` only, so `llm` reflects spoken replies | `test_tool_call_turns_are_not_counted_as_llm` |
| Scripted first message | Not counted in `e2e` (it isn't a reply to the caller) | `test_e2e_only_counts_generated_replies` |
| New timing metric names | Listed; known-but-unreported names stay quiet | `test_new_metric_names_are_reported` |
| Agent's TTS model isn't a low-cost one | `make evals` stops before spending credits | `test_cost_guard_blocks_other_models` |
| Analysis still running, or never finishing | Polls, then `TimeoutError` | `test_wait_for_analysis_polls_until_done`, `test_wait_for_analysis_times_out` |

## Resilience

Tested with the [fault injection harness](../../harness/faults/README.md) between the tools and the airline (`test_resilience.py`).

| Case | Behaviour | Test |
|---|---|---|
| Airline slow | Same results; only latency changes | `test_latency_does_not_change_results` |
| 500, 503, 429, connection refused, or timeout | `airline_unavailable`, audited | `test_airline_failures_become_airline_unavailable` |
| Airline fails once, then recovers | The next call succeeds | `test_flaky_airline_recovers` |
| Confirm failed but definitely didn't apply (never sent, or re-check shows unchanged) | `airline_unavailable`, and the quote is kept: retrying the same `confirmation_id` works until it expires | `test_retry_after_failed_confirm_succeeds`, `test_still_failing_airline_keeps_the_quote_retryable`, `test_restored_quote_still_expires` |
| First confirm lands late, after the re-check | The retry sends the same idempotency key, so the airline returns the stored result and the seat moves once | `test_late_landing_write_is_not_applied_twice` |
| Clear rejection (409 full, other 4xx) | The quote is used up; a retry gets `unknown_confirmation` | `test_clear_rejection_uses_up_the_quote` |
| Status unknown after a failed re-check | The quote isn't kept; the agent looks the booking up instead of confirming again | `test_lost_write_with_failed_recheck_is_status_unknown` |
| Same idempotency key twice at the airline | Applied once; the second call returns the stored result | `test_same_idempotency_key_applies_once` |
| Key reused for a different flight | 422; nothing applied | `test_key_reused_for_different_request_is_422` |
| Dry-run confirm | Never contacts the airline | `test_dry_run_confirm_never_reaches_airline` |
| Non-JSON reply (broken 200, HTML 404 from a proxy) | `airline_unavailable`, never "booking not found" *(was gap 1)* | `test_non_json_reply_is_airline_unavailable`, `test_non_json_search_reply_is_airline_unavailable` |
| Confirm applied but its reply lost | Booking re-read; reported as `rebooked` with `reconciled: true` *(was gap 2)* | `test_lost_write_is_reconciled_as_rebooked` |
| Reply lost **and** the re-check fails | `rebook_status_unknown`: "don't confirm again, look it up"; the prompt tells the agent to call `lookup_booking` | `test_lost_write_with_failed_recheck_is_status_unknown` |
| Confirm timed out, got a 5xx, or got an unreadable reply, but wasn't applied | Re-checked, then `airline_unavailable` | `test_unclear_confirm_not_applied_is_airline_unavailable`, `test_unclear_confirm_is_rechecked` |
| Confirm couldn't connect at all | `airline_unavailable` with no re-check: the request was never sent | `test_confirm_connect_error_skips_recheck` |
| Confirm got another 4xx | Treated as a clear answer, no re-check | `test_confirm_other_4xx_is_not_rechecked` |

## Eval scenarios

`happy_path`, `wrong_last_name`, `full_flight`, `user_declines`, `out_of_scope`, `different_route`. Each starts from a fresh in-memory airline and is forced into dry-run mode. They're defined in `harness/evals/scenarios.py`.

Latency stages:

| Stage | Metric | Meaning |
|---|---|---|
| `stt` | `convai_asr_trailing_service_latency` | Speech-to-text; **unverified**, since text sessions don't produce it |
| `llm` | `convai_llm_service_ttfb` | LLM time to first output, spoken-reply turns only |
| `llm_tool` | `convai_llm_tool_request_generation_latency` | LLM time to produce a tool call |
| `tts` | `convai_tts_service_ttfb` | Text-to-speech time to first audio |
| `e2e` | `convai_ttf_audio_since_silence` | Caller goes quiet → first agent audio |

**Cost guard:** `make evals` first checks that the live agent uses a low-cost TTS model (`eleven_flash_v2` or `eleven_turbo_v2`) and stops otherwise. Live tests are also excluded from every pytest run by default (`pyproject.toml`), so only `make evals` can start them.

## Live results

First live session, 2026-10-02: a dry-run rebooking typed through `make chat`. TTS was `eleven_v4_turbo` with expressive mode on, before the switch to Flash. The trimmed conversation is the recorded fixture `harness/replay/conversation_details.json`.

- **Behaviour:** lookup → search → quote → read-back → "yes" → confirm (dry run). The audit log has 4 `ok` calls, and the booking was unchanged.
- **Judge:** all four criteria `success`.
- **Latency** (one session, so small samples):

  | Stage | n | p50 | p95 |
  |---|---|---|---|
  | `llm` | 4 | 188 ms | 269 ms |
  | `llm_tool` | 4 | 438 ms | 629 ms |
  | `tts` | 5 | 89 ms | 91 ms |
  | `e2e` | 4 | 1033 ms | 1267 ms |
  | `stt` | 0 | n/a | n/a |

- **Cost:** 1,658 credits, of which 1,499 were billed as voice call minutes for the whole 4.5-minute session. Session length, not just the TTS model, drives cost.

**Evals, same day: all six scenarios pass** the rule checks and all four judge criteria. They ran in two batches:

| Batch | Scenarios | TTS | Duration | Credits each |
|---|---|---|---|---|
| 1 | `happy_path`, `wrong_last_name`, `full_flight`, `user_declines` | `eleven_v4_turbo` | 19–26 s | 183–306 |
| 2 | `out_of_scope`, `different_route` | `eleven_flash_v2` | 15–21 s | 199–305 |

- `out_of_scope`: the agent declined the cancel-and-refund request twice and called no tools.
- `different_route`: the agent looked up the booking, refused to change route, and never tried a quote.
- **Cost:** switching to Flash v2 showed no visible per-scenario saving. The voice-minute charge (168–236 credits in batch 2) dominates and doesn't track the TTS model. The per-second rate also differed between eval sessions (~11 credits/s) and the long chat (~5.5 credits/s), for reasons not visible in the data. With samples this small, session length is still the main cost lever.
- **Batch 2 latency** (Flash v2, small samples): `llm` p50 279 / p95 496 ms, `llm_tool` 419 ms (n=1), `tts` p50 123 / p95 138 ms, `e2e` p50 499 / p95 977 ms.

## Running it live

1. Put `ELEVENLABS_API_KEY` and a stock `ELEVENLABS_VOICE_ID` in `.env`.
2. `make agent`, then copy the printed id into `ELEVENLABS_AGENT_ID`.
3. `make chat` (start `make airline` in another terminal first) for a quick text check.
4. `make evals` runs all six scenarios (costs credits). To run some of them: `make evals ONLY=out_of_scope,different_route`. An unknown name fails before anything is spent.
5. For speech-to-text latency, use a voice session (`make talk`, which needs `pyaudio`), then `make latency IDS="<conversation id>"`.

## Open questions

- **STT metric name:** still unverified; needs one voice session.
- **Cost of text sessions:** a typed session is billed as voice minutes for as long as it's open. Whether a text-only session setting would be cheaper is untested.
- **Websocket replay fixture:** `rebook_conversation.jsonl` is still hand-written; recording it needs a capture mode in `session.py`.
- **SDK upgrades:** the replay test uses a private SDK method (`Conversation._handle_message`), which is why `elevenlabs` is pinned to `~=2.70.0`.
- **Using your own voice:** it's blocked by the stock-voice guard; using it would need an explicit allowlist.

## Trade-offs

See `DECISIONS.md`: tools over HTTP; two-step gate and default dry run; client tools instead of webhooks; agent defined in code; our own eval runner instead of ElevenLabs simulations; text-driven evals; ElevenLabs grader as judge; latency stages; Flash v2 TTS and the cost guard.

## Run

```bash
make test
```
