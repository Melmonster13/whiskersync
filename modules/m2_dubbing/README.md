# m2 — Dubbing task state machine

**Problem:** a dubbing job fans out into one task per target language, and each task runs a multi-stage pipeline where any stage can fail. The orchestrator needs to know exactly what each task may do next, retry without redoing paid work, and report a single status for the whole job. **Approach:** every allowed move lives in one explicit `(state, event) → state` table; anything else raises `InvalidTransition` instead of being silently ignored. A retry resumes the stage that failed, up to `max_retries`, and each task keeps a history of every move. `job_status()` combines the tasks into one job status. **Result:** 54 tests, including every illegal `(state, event)` pair generated from the table, retries resuming each stage, running out of retries, and 10 job-status combinations.

## Usage

```python
from modules.m2_dubbing.state_machine import DubbingTask, job_status

task = DubbingTask("es", max_retries=3)
task.start()               # TRANSCRIBING
task.step_done()           # TRANSLATING
task.fail("api 503")       # FAILED (failed_stage=TRANSLATING, error="api 503")
task.retry()               # TRANSLATING again, retries=1
job_status([task, DubbingTask("fr")])   # JobStatus.IN_PROGRESS
```

## Rules

- **States:** `QUEUED → TRANSCRIBING → TRANSLATING → SYNTHESIZING → COMPLETED`, plus `FAILED` and `CANCELLED`.
- **Events:** `start`, `step_done`, `fail`, `retry`, `cancel`.
- **Final states:** `COMPLETED`, `CANCELLED`, and `FAILED` once retries run out. A final task refuses every event.
- **Job status:**

  | Tasks | Job |
  |---|---|
  | All queued | `QUEUED` |
  | Any task not final (including failed with retries left) | `IN_PROGRESS` |
  | All completed | `COMPLETED` |
  | All cancelled | `CANCELLED` |
  | Some completed, the rest failed or cancelled | `PARTIAL` |
  | None completed, some failed | `FAILED` |

## Edge cases

| Case | Behaviour | Test |
|---|---|---|
| Any move not in the table | `InvalidTransition`; state and history unchanged | `test_illegal_transitions_raise` |
| Failure in each working stage | Retry resumes that stage | `test_retry_resumes_failed_stage` |
| Retries run out | Task is final; retry and cancel both raise | `test_retries_exhausted` |
| `max_retries=0` | The first failure is final | `test_zero_retries_first_failure_is_final` |
| Cancel a failed task that can still retry | Allowed | `test_legal_transitions` |
| Cancel a completed or cancelled task | `InvalidTransition` | `test_cannot_cancel_finished_task` |
| Error on repeated failures | Keeps the latest error | `test_retries_exhausted` |
| History | Records `(from, event, to)` for every move, including retries | `test_happy_path`, `test_history_records_fail_and_retry` |
| Failed task with retries left in a job | Job stays `IN_PROGRESS` | `test_job_status` |
| Job with no tasks | `ValueError` | `test_job_status_empty_raises` |

**Known limit:** a failed task with retries left keeps the job `IN_PROGRESS` until something retries or cancels it. The orchestrator owns that decision; the state machine won't give up on its own.

## Trade-offs

See `DECISIONS.md`: retry resumes the failed stage; illegal moves raise instead of no-op; how retryable failures and `PARTIAL` count in job status.

## Run

```bash
.venv/bin/pytest modules/m2_dubbing
```
