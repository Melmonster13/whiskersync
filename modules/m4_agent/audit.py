"""Append-only JSONL audit log: one line per agent tool call."""

import json
from datetime import datetime, timezone
from pathlib import Path


class AuditLog:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        conversation_id: str,
        tool: str,
        args,
        outcome: str,
        dry_run: bool,
        error: str | None = None,
    ) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "conversation_id": conversation_id,
            "tool": tool,
            "args": args,
            "outcome": outcome,
            "error": error,
            "dry_run": dry_run,
        }
        with self.path.open("a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line]
