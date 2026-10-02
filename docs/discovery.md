# Discovery notes: WhiskerSync Air rebooking agent

> **Simulated engagement.** WhiskerSync Air is a fictional airline, and these notes are a practice discovery written as if for a real customer. All data in this repo is synthetic. Where I'd need numbers from a real customer, I say so.

## The problem

WhiskerSync Air's contact centre handles a steady stream of **"move me to a different flight"** calls. In a real engagement I'd expect those to peak around schedule changes and bad weather, exactly when queues are longest. The work is repetitive: verify the caller, find options on the same route, confirm one, update the booking. That makes it a good first candidate for a voice agent, as long as it never changes a booking the caller didn't clearly agree to.

## Who I'd talk to, and what they care about

| Stakeholder | What they care about |
|---|---|
| Contact-centre lead | Shorter queues at peak; agents freed for complex calls; a clean hand-off when the AI can't help |
| IT / integration | No direct database access; a stable, versioned booking API; retries that can't double-book; working under load and partial outages |
| Compliance / risk | Caller verification; an audit trail of every action; no change without explicit consent; PII handling and retention |
| The caller | Not repeating themselves; a clear read-back before anything changes; a fast answer, with natural pauses rather than dead air |

## Requirements, and where this repo meets them

| Requirement | How it's met | Where |
|---|---|---|
| Verify the caller before revealing or changing anything | Confirmation code **and** last name; a wrong name looks the same as an unknown code | `tools.py`, mock airline `GET /bookings/{code}` |
| No change without a clear "yes" | Two steps: `quote_rebook` never writes; `confirm_rebook` needs the single-use, 5-minute quote id. The prompt requires a read-back and an explicit yes | `tools.py`, `config.py` |
| Safe by default | Every confirm is a dry run unless `DRY_RUN=false` | `tools.py` |
| Every action auditable | One JSON line per tool call, including rejected and failed calls | `audit.py` |
| Stays in scope | Same-route moves only; refunds and cancellations are politely declined | Prompt; evals `out_of_scope`, `different_route` |
| Survives a slow or failing backend | Outages become a speakable "airline unavailable"; unclear writes are re-checked; retries carry an idempotency key | m4 README, *Resilience* |
| Measurable | Six scripted scenarios, rule checks, an LLM judge, p50/p95 latency per stage | `harness/evals/` |

## How I'd measure success

- **Containment rate:** the share of rebooking calls completed without a human.
- **Wrong-change rate:** bookings changed without valid consent. **Target: zero**; that's the safety bar, not a goal to optimise.
- **Response latency:** p95 time from the caller going quiet to the agent's first audio (`e2e`).
- **Average handle time** for contained calls, compared with human-handled ones.
- **Escalation quality:** whether the human agent gets the context and the caller doesn't repeat themselves.

## Open questions for the customer

1. **Volumes:** rebooking calls per month, and how peaky they are. These drive the ROI model (`roi.md`).
2. **Source of truth:** which system owns bookings and seat inventory, and does its write API support **idempotency keys**? If not, I'd need a reconciliation design with their team.
3. **Fare rules:** are same-route moves always free, or are there fare differences the agent would need to quote?
4. **Identity:** is code plus last name enough, or do they need an extra factor for some bookings?
5. **PII and retention:** how long can transcripts and audio be kept, and in which region?
6. **Hand-off:** how does an escalated call reach a human, and what context travels with it?
7. **Languages and voice:** English only at first? Any brand voice requirements? *(This build uses stock voices only.)*

## What I deliberately left out of this build

Payments and fare differences, cancellations and refunds, multi-passenger bookings, telephony (calls run through the SDK, not a phone number), and a human hand-off. Each is a scope decision for the customer, not a technical blocker.
