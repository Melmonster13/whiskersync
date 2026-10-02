"""Drill 3 — Task order with dependencies.                      Target: 25 min

Given task names and dependencies (a, b) meaning "a must run before b", return an order
that runs every task exactly once and respects every dependency.

When several tasks are ready at the same time, pick the alphabetically smallest first,
so the answer is unique.

    task_order(["translate", "transcribe", "synthesize"],
               [("transcribe", "translate"), ("translate", "synthesize")])
        ->  ["transcribe", "translate", "synthesize"]

    task_order(["b", "a", "c"], [])  ->  ["a", "b", "c"]

Constraints:
- A cycle (including a task depending on itself) raises ValueError.
- A dependency naming an unknown task raises ValueError.
- Duplicate dependencies are allowed and count once.

Expected: O((V + E) log V) time with a heap for the ready set.
"""


def task_order(tasks: list[str], deps: list[tuple[str, str]]) -> list[str]:
    raise NotImplementedError("solve me")
