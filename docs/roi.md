# ROI model: WhiskerSync Air rebooking agent

> **Simulated engagement.** The AI cost below is **measured** in this repo. Everything about the airline (volumes, human cost, containment) is a **placeholder** I'd replace with the customer's data. Don't read the totals as a forecast.

## Measured: what an AI-handled call costs

From ElevenLabs' own per-conversation billing figures, with the agent on `eleven_v4_turbo` (free tier, 2026-10-02):

| Session type | Credits per minute | USD per minute |
|---|---|---|
| Eval scenarios (busy: a turn every few seconds) | 617 | **$0.062** |
| Typed chat (long pauses while typing) | 364 | $0.036 |
| Voice call with headphones (full rebooking, 104 s) | 438 | $0.044 |

- **Billing has two parts:** LLM credits per conversation, plus a **per-second call charge of about 5.5 credits/s** on `eleven_v4_turbo`. The same charge was about 11.2 credits/s on `eleven_flash_v2`, so the model choice matters (see the m4 README).
- **Exchange rate:** ElevenLabs reported about **$0.10 per 1,000 credits** on every session.
- **Speech-to-text is included in the call charge:** the voice call's charge was 5.50 credits/s, the same as text sessions on `eleven_v4_turbo`.
- I use the busier rate, **$0.062/min**, as the conservative figure.

## Inputs: placeholders to replace with customer data

None of these is a real or researched figure. They're **PLACEHOLDERS**, chosen only to show how the model works.

| Input | Value | Status | Why it matters |
|---|---|---|---|
| Rebooking calls per month (V) | 20,000 | **PLACEHOLDER** | Scales everything |
| Fully loaded cost of a human-handled call (H) | $6.00 | **PLACEHOLDER** | The saving per contained call |
| Containment rate (c) | 40% | **PLACEHOLDER** | Share of calls the agent completes alone |
| AI minutes on a contained call | 3.0 | **PLACEHOLDER** | Real callers are slower than the scripted evals (14–26 s, measured) |
| AI minutes before hand-off on an escalated call | 1.5 | **PLACEHOLDER** | Escalated calls still cost AI time |
| AI cost per minute | $0.062 | **Measured** (see above) | The only measured input |

## The model

The formulas are the substance; every number computed below depends on the placeholders.

- AI cost of a contained call: **A_full** = 3.0 min *(placeholder)* × $0.062 *(measured)* = **$0.185** *(illustrative)*
- AI cost of an escalated call: **A_partial** = 1.5 min *(placeholder)* × $0.062 *(measured)* = **$0.092** *(illustrative)*, on top of the human cost
- Net saving per call: **c × (H − A_full) − (1 − c) × A_partial**
- Monthly saving: **V × net saving per call**
- **Break-even containment** (net saving = 0): **A_partial ÷ (H − A_full + A_partial)**. With the placeholders, about **1.6%** *(illustrative)*.

## Sensitivity: monthly saving (illustrative)

> **Every figure in this table comes from the placeholders:** H = $6.00 per human-handled call, 3.0 / 1.5 AI minutes per call, and the volumes and containment rates shown. Only the $0.062/min AI cost is measured. Don't quote these as expected savings.

| Containment *(placeholder)* ↓ / Calls per month *(placeholder)* → | 5,000 | 20,000 | 50,000 |
|---|---|---|---|
| 20% | $5,446 | $21,784 | $54,460 |
| 40% | $11,354 | $45,415 | $113,537 |
| 60% | $17,261 | $69,045 | $172,613 |

With the same placeholders, the ElevenLabs platform spend inside these figures would be about **$2,200–$3,000 a month** at 20,000 calls *(illustrative)*: measured per-minute cost × placeholder minutes × placeholder volume.

## What this model leaves out

These are the real costs I'd put in front of a customer next to the table above:

- **Build and integration:** connecting to the booking API (including idempotency support), the hand-off, monitoring. Usually the largest cost, and a one-off.
- **Telephony** per-minute charges, if calls come in over the phone network.
- **The production ElevenLabs plan:** these rates come from the free tier and may differ.
- **Human review** of agent-handled changes during rollout.
- **Risk:** a wrong change costs far more than a saved call. That's why the wrong-change rate target is zero and rollout starts in dry run.

## What a pilot would measure to replace the placeholders

1. Real containment, from shadow-mode outcomes against human outcomes.
2. Real handle time for contained and escalated calls, which gives the AI minutes per call.
3. The customer's actual cost per human-handled call.
4. Credits per call on the production plan, read from ElevenLabs' conversation details, as this repo already does.

The conclusion I'd expect to hold even with real numbers: **the AI platform cost is small next to human handling time**. The business case depends on containment and on never making a wrong change, not on the per-minute rate. The per-minute rate still matters at scale, and it's why the agent uses the voice model measured cheapest.
