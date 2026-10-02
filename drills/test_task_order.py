import pytest

from drills.task_order import task_order

# Remove this marker once the drill is solved.
pytestmark = pytest.mark.xfail(raises=NotImplementedError, reason="drill not solved yet")


@pytest.mark.parametrize(
    "tasks, deps, expected",
    [
        ([], [], []),
        (["a"], [], ["a"]),
        (["b", "a", "c"], [], ["a", "b", "c"]),                          # no deps: alphabetical
        (
            ["translate", "transcribe", "synthesize"],
            [("transcribe", "translate"), ("translate", "synthesize")],
            ["transcribe", "translate", "synthesize"],                   # chain
        ),
        (
            ["mix", "tts_es", "tts_fr", "stt"],
            [("stt", "tts_es"), ("stt", "tts_fr"), ("tts_es", "mix"), ("tts_fr", "mix")],
            ["stt", "tts_es", "tts_fr", "mix"],                          # diamond
        ),
        (["a", "b", "c"], [("c", "a")], ["b", "c", "a"]),                # tie-break picks b before c
        (["a", "b"], [("a", "b"), ("a", "b")], ["a", "b"]),              # duplicate dep
        (["z", "y", "x"], [("z", "x")], ["y", "z", "x"]),                # disconnected parts
    ],
)
def test_task_order(tasks, deps, expected):
    assert task_order(tasks, deps) == expected


@pytest.mark.parametrize(
    "tasks, deps",
    [
        (["a"], [("a", "a")]),                                  # self-dependency
        (["a", "b"], [("a", "b"), ("b", "a")]),                 # 2-cycle
        (["a", "b", "c", "d"], [("a", "b"), ("b", "c"), ("c", "b"), ("a", "d")]),  # cycle off a valid start
        (["a"], [("a", "ghost")]),                              # unknown task
    ],
)
def test_invalid_raises(tasks, deps):
    with pytest.raises(ValueError):
        task_order(tasks, deps)
