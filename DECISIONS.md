# Decisions

Format: `date | choice | why`

- 2026-10-01 | pytest config in `pyproject.toml`, not `pytest.ini` | one file for tool config as the repo grows
- 2026-10-01 | `live` and `evals` markers; CI runs `-m "not live and not evals"` | CI never makes live API calls or spends credits
- 2026-10-01 | m3 resolver: nearest grant up the tree wins, not highest role on the path | lets a child downgrade or deny (`Role.NONE`) what a parent grants
- 2026-10-01 | m3 resolver: on one node, a user grant beats group grants; among groups, highest wins | a user-specific grant is the more deliberate override
- 2026-10-01 | m1 sync: words are active on `[start, end)` | at a shared boundary the next word wins, so there's never a frame with two active words
- 2026-10-01 | m1 sync: in gaps, no active word but the last speaker holds until the next word | avoids speaker label flicker during pauses
- 2026-10-01 | m1 sync: overlapping words allowed; most recently started word still in progress wins | real diarized speech has crosstalk; lookup walks back from the bisect index with a prefix "latest end" to stop early
- 2026-10-01 | m2 state machine: retry resumes the stage that failed, not the whole pipeline | don't pay again for transcription when only TTS failed
- 2026-10-01 | m2 state machine: illegal (state, event) pairs raise instead of no-op | silent no-ops hide orchestrator bugs
- 2026-10-01 | m2 job status: a failed task with retries left counts as in progress; some languages done + rest failed/cancelled = PARTIAL | the job isn't settled until every task is final, and partial output is still deliverable
- 2026-10-01 | m4 tools reach the mock airline over HTTP, not SQLite directly | mirrors a real customer integration; lets fault injection test timeouts later; tests stay offline via ASGI transport
- 2026-10-01 | m4 rebooking is two-step: `quote_rebook` (no write, single-use id, 5 min TTL) then `confirm_rebook`; `DRY_RUN` on unless explicitly false | a gated action needs explicit confirmation, and the safe default is no write
- 2026-10-01 | m4 `quote_rebook` re-verifies last name; mock airline returns the same 404 for wrong name and unknown code | a confirmation code alone shouldn't allow changes or confirm a booking exists
- 2026-10-01 | m4 IDs are alphanumeric-only before going into URL paths | blocks path injection (`../`) from model-generated arguments
- 2026-10-01 | mock airline endpoints are `async` | keeps every SQLite call on the event loop thread, so one shared connection is safe
- 2026-10-01 | m4 agent defined in code (`config.py` + `provision.py`), tool schemas generated from `TOOL_PARAMS` | reviewable, reproducible agent; tool schema can't drift from the dispatcher
- 2026-10-01 | m4 tools run as SDK client tools in our process, not server webhooks | no public endpoint needed for a local sandbox; audit log and dry-run stay on our side
- 2026-10-01 | `provision.py` refuses any voice whose category isn't `premade` | enforces stock-voices-only; using my own voice would need an explicit allowlist
- 2026-10-01 | bridge strips SDK-injected `tool_call_id` and returns errors as `{ok: false}` results, not raised exceptions | dispatcher stays strict on unknown args; the agent gets a message it can explain instead of a generic error
- 2026-10-01 | audit `conversation_id` is a local session id; the ElevenLabs id is logged at session end | the SDK only exposes the conversation id publicly after the session ends
- 2026-10-01 | replay fixture is hand-written in the SDK message format and run through the SDK's own (private) `_handle_message` | no API key yet to record; exercises the real tool-call path offline; re-record later
- 2026-10-01 | evals use our own runner, not ElevenLabs simulated conversations | simulation is deprecated and mocks tool results, so it would never exercise our tools, airline, or audit log
- 2026-10-01 | evals drive the agent with scripted text turns | deterministic and cheap; LLM and TTS latency are real, STT shows n/a; voice sessions get STT numbers via `make latency`
- 2026-10-01 | each eval scenario gets a fresh in-memory airline over ASGI transport and is forced dry-run | scenarios can't affect each other; no server to start; evals can never change data
- 2026-10-01 | eval pass = rule-based checks (audit log + final booking) and no ElevenLabs judge `failure`; `unknown` doesn't fail | outcomes are checked deterministically; the judge covers wording and behavior the rules can't
- 2026-10-01 | judge is ElevenLabs evaluation criteria on the agent, not a separate LLM | no second provider or key; every conversation gets graded, not just evals
- 2026-10-01 | latency reported as nearest-rank p50/p95 per stage; metric key names and seconds unit are unverified, unmapped keys always printed | the SDK doesn't define the names; fix the mapping after the first live run instead of guessing silently
- 2026-10-01 | drills are stubs with tests marked `xfail(raises=NotImplementedError)`; tests verified against uncommitted reference solutions | practice material, not answers; CI stays green on stubs but a wrong solution still fails
- 2026-10-01 | `elevenlabs` pinned to `~=2.70.0` | the Conversation API is marked beta and the replay test touches a private method
