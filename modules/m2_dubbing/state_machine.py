"""Per-language dubbing task state machine, plus a job-level status across languages.

QUEUED -> TRANSCRIBING -> TRANSLATING -> SYNTHESIZING -> COMPLETED
Any working stage can FAIL; RETRY resumes the stage that failed, up to max_retries.
Any non-final state can be CANCELLED. Illegal (state, event) pairs raise InvalidTransition.
"""

from dataclasses import dataclass, field
from enum import Enum


class TaskState(Enum):
    QUEUED = "queued"
    TRANSCRIBING = "transcribing"
    TRANSLATING = "translating"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Event(Enum):
    START = "start"
    STEP_DONE = "step_done"
    FAIL = "fail"
    RETRY = "retry"
    CANCEL = "cancel"


class JobStatus(Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class InvalidTransition(Exception):
    pass


S, E = TaskState, Event
WORKING = (S.TRANSCRIBING, S.TRANSLATING, S.SYNTHESIZING)

# None = resume the stage that failed (resolved at runtime).
TRANSITIONS: dict[tuple[TaskState, Event], TaskState | None] = {
    (S.QUEUED, E.START): S.TRANSCRIBING,
    (S.TRANSCRIBING, E.STEP_DONE): S.TRANSLATING,
    (S.TRANSLATING, E.STEP_DONE): S.SYNTHESIZING,
    (S.SYNTHESIZING, E.STEP_DONE): S.COMPLETED,
    **{(s, E.FAIL): S.FAILED for s in WORKING},
    (S.FAILED, E.RETRY): None,
    **{(s, E.CANCEL): S.CANCELLED for s in (S.QUEUED, *WORKING, S.FAILED)},
}


@dataclass
class DubbingTask:
    language: str
    max_retries: int = 3
    state: TaskState = TaskState.QUEUED
    retries: int = 0
    error: str | None = None
    failed_stage: TaskState | None = None
    history: list[tuple[TaskState, Event, TaskState]] = field(default_factory=list)

    @property
    def is_final(self) -> bool:
        if self.state is S.FAILED:
            return self.retries >= self.max_retries
        return self.state in (S.COMPLETED, S.CANCELLED)

    def apply(self, event: Event, error: str | None = None) -> TaskState:
        if (self.state, event) not in TRANSITIONS or self.is_final:
            raise InvalidTransition(f"{event.value} not allowed from {self.state.value}")

        if event is E.RETRY:
            target = self.failed_stage
            self.retries += 1
        else:
            target = TRANSITIONS[(self.state, event)]
            if event is E.FAIL:
                self.failed_stage = self.state
                self.error = error

        self.history.append((self.state, event, target))
        self.state = target
        return target

    def start(self) -> TaskState:
        return self.apply(E.START)

    def step_done(self) -> TaskState:
        return self.apply(E.STEP_DONE)

    def fail(self, error: str) -> TaskState:
        return self.apply(E.FAIL, error)

    def retry(self) -> TaskState:
        return self.apply(E.RETRY)

    def cancel(self) -> TaskState:
        return self.apply(E.CANCEL)


def job_status(tasks: list[DubbingTask]) -> JobStatus:
    if not tasks:
        raise ValueError("job has no tasks")
    if not all(t.is_final for t in tasks):
        if all(t.state is S.QUEUED for t in tasks):
            return JobStatus.QUEUED
        return JobStatus.IN_PROGRESS

    states = {t.state for t in tasks}
    if states == {S.COMPLETED}:
        return JobStatus.COMPLETED
    if states == {S.CANCELLED}:
        return JobStatus.CANCELLED
    if S.COMPLETED in states:
        return JobStatus.PARTIAL
    return JobStatus.FAILED
