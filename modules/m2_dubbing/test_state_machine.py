import pytest

from modules.m2_dubbing.state_machine import (
    TRANSITIONS,
    DubbingTask,
    Event,
    InvalidTransition,
    JobStatus,
    TaskState,
    job_status,
)

S, E = TaskState, Event
WORKING = [S.TRANSCRIBING, S.TRANSLATING, S.SYNTHESIZING]


def task_in(state, retries=0, max_retries=3, failed_stage=S.TRANSLATING):
    task = DubbingTask("es", max_retries=max_retries, state=state, retries=retries)
    if state is S.FAILED:
        task.failed_stage = failed_stage
    return task


def test_happy_path():
    task = DubbingTask("es")
    assert task.start() is S.TRANSCRIBING
    assert task.step_done() is S.TRANSLATING
    assert task.step_done() is S.SYNTHESIZING
    assert task.step_done() is S.COMPLETED
    assert task.is_final
    assert task.history == [
        (S.QUEUED, E.START, S.TRANSCRIBING),
        (S.TRANSCRIBING, E.STEP_DONE, S.TRANSLATING),
        (S.TRANSLATING, E.STEP_DONE, S.SYNTHESIZING),
        (S.SYNTHESIZING, E.STEP_DONE, S.COMPLETED),
    ]


@pytest.mark.parametrize(
    "state, event, expected",
    [
        (S.QUEUED, E.START, S.TRANSCRIBING),
        (S.TRANSCRIBING, E.STEP_DONE, S.TRANSLATING),
        (S.TRANSLATING, E.STEP_DONE, S.SYNTHESIZING),
        (S.SYNTHESIZING, E.STEP_DONE, S.COMPLETED),
        (S.TRANSCRIBING, E.FAIL, S.FAILED),
        (S.TRANSLATING, E.FAIL, S.FAILED),
        (S.SYNTHESIZING, E.FAIL, S.FAILED),
        (S.QUEUED, E.CANCEL, S.CANCELLED),
        (S.TRANSCRIBING, E.CANCEL, S.CANCELLED),
        (S.TRANSLATING, E.CANCEL, S.CANCELLED),
        (S.SYNTHESIZING, E.CANCEL, S.CANCELLED),
        (S.FAILED, E.CANCEL, S.CANCELLED),   # failed but retryable
    ],
)
def test_legal_transitions(state, event, expected):
    assert task_in(state).apply(event, error="boom") is expected


@pytest.mark.parametrize(
    "state, event",
    [(s, e) for s in TaskState for e in Event if (s, e) not in TRANSITIONS],
)
def test_illegal_transitions_raise(state, event):
    task = task_in(state)
    with pytest.raises(InvalidTransition):
        task.apply(event)
    assert task.state is state
    assert task.history == []


@pytest.mark.parametrize("stage", WORKING)
def test_retry_resumes_failed_stage(stage):
    task = task_in(stage)
    task.fail("tts timeout")
    assert task.state is S.FAILED
    assert task.failed_stage is stage
    assert task.error == "tts timeout"
    assert task.retry() is stage
    assert task.retries == 1


def test_retries_exhausted():
    task = DubbingTask("fr", max_retries=2)
    task.start()
    for _ in range(2):
        task.fail("boom")
        task.retry()
    task.fail("boom again")
    assert task.is_final
    with pytest.raises(InvalidTransition):
        task.retry()
    with pytest.raises(InvalidTransition):
        task.cancel()
    assert task.state is S.FAILED
    assert task.error == "boom again"


def test_zero_retries_first_failure_is_final():
    task = DubbingTask("de", max_retries=0)
    task.start()
    task.fail("boom")
    assert task.is_final
    with pytest.raises(InvalidTransition):
        task.retry()


@pytest.mark.parametrize("state", [S.COMPLETED, S.CANCELLED])
def test_cannot_cancel_finished_task(state):
    with pytest.raises(InvalidTransition):
        task_in(state).cancel()


def test_history_records_fail_and_retry():
    task = DubbingTask("ja")
    task.start()
    task.step_done()
    task.fail("translation api 503")
    task.retry()
    assert task.history[-2:] == [
        (S.TRANSLATING, E.FAIL, S.FAILED),
        (S.FAILED, E.RETRY, S.TRANSLATING),
    ]


def exhausted():
    return task_in(S.FAILED, retries=3)


@pytest.mark.parametrize(
    "tasks, expected",
    [
        ([task_in(S.QUEUED), task_in(S.QUEUED)], JobStatus.QUEUED),
        ([task_in(S.QUEUED), task_in(S.TRANSLATING)], JobStatus.IN_PROGRESS),
        ([task_in(S.COMPLETED), task_in(S.SYNTHESIZING)], JobStatus.IN_PROGRESS),
        ([task_in(S.COMPLETED), task_in(S.FAILED)], JobStatus.IN_PROGRESS),   # failed but retryable
        ([task_in(S.COMPLETED), task_in(S.COMPLETED)], JobStatus.COMPLETED),
        ([task_in(S.COMPLETED), exhausted()], JobStatus.PARTIAL),
        ([task_in(S.COMPLETED), task_in(S.CANCELLED)], JobStatus.PARTIAL),
        ([exhausted(), exhausted()], JobStatus.FAILED),
        ([exhausted(), task_in(S.CANCELLED)], JobStatus.FAILED),
        ([task_in(S.CANCELLED), task_in(S.CANCELLED)], JobStatus.CANCELLED),
    ],
)
def test_job_status(tasks, expected):
    assert job_status(tasks) is expected


def test_job_status_empty_raises():
    with pytest.raises(ValueError):
        job_status([])
