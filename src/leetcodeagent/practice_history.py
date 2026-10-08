"""Local, append-only history of LeetCode practice activity."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .problems import Problem


STATUSES = {"recommended", "skipped", "attempted", "solved", "removed"}
ENTRY_PATTERN = re.compile(
    r"\s*(?:-\s*)?([1-9]\d*)\.\s+([^|\n]+?)\s*\|\s*(easy|medium|hard)\s*",
    re.IGNORECASE,
)


class PracticeHistory:
    """Keep practice events separate from the solved-problem memory file."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        events = []
        for line_number, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"Invalid practice history on line {line_number}."
                ) from error
            if (
                not isinstance(event, dict)
                or type(event.get("number")) is not int
                or event["number"] <= 0
                or not isinstance(event.get("status"), str)
                or event.get("status") not in STATUSES
                or not isinstance(event.get("title"), str)
            ):
                raise ValueError(f"Invalid practice history on line {line_number}.")
            events.append(event)
        return events

    def seen_numbers(self) -> set[int]:
        """Avoid recommending previously shown problems, even after a restart."""
        return {
            event["number"]
            for event in self.events()
            if event["status"] in {"recommended", "skipped", "attempted"}
        }

    def current_status(self, number: int) -> str | None:
        for event in reversed(self.events()):
            if event["number"] == number:
                return event["status"]
        return None

    def latest_recommendation(self) -> Problem | None:
        """Restore the last recommendation for follow-up questions."""
        for event in reversed(self.events()):
            if event["status"] == "recommended":
                return Problem(
                    event["number"],
                    event["title"],
                    event.get("difficulty", ""),
                    event.get("topic", ""),
                    event.get("slug", ""),
                )
        return None

    def record(self, problem: Problem, status: str) -> dict[str, Any]:
        if status not in STATUSES:
            raise ValueError(f"Unknown practice status: {status}")
        if problem.number <= 0 or not problem.title.strip():
            raise ValueError("A practice event needs a problem number and title.")

        current = next(
            (event for event in reversed(self.events()) if event["number"] == problem.number),
            None,
        )
        if current is not None and current["status"] == status:
            return current

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": status,
            "number": problem.number,
            "title": problem.title,
            "difficulty": problem.difficulty,
            "topic": problem.topic,
            "slug": problem.slug,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as history_file:
            history_file.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def record_entry(self, entry: str, status: str) -> bool:
        """Record a numbered memory entry; return false for older formats."""
        match = ENTRY_PATTERN.fullmatch(entry)
        if match is None:
            return False
        number, title, difficulty = match.groups()
        self.record(Problem(int(number), title.strip(), difficulty.lower(), ""), status)
        return True

    def summary(
        self,
        solved_numbers: set[int],
        *,
        status: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Return current entries and counts, optionally filtered by status."""
        if status is not None and status not in STATUSES:
            raise ValueError(f"Unknown practice status: {status}")
        if limit < 1 or limit > 50:
            raise ValueError("History limit must be between 1 and 50.")
        events = self.events()
        counts = {status: 0 for status in STATUSES}
        entries = []
        seen = set()
        for event in reversed(events):
            number = event["number"]
            if number in seen:
                continue
            seen.add(number)
            current_status = event["status"]
            if number in solved_numbers:
                current_status = "solved"
            elif current_status == "solved":
                # memory.md is authoritative when a solved record was removed by hand.
                current_status = "removed"
            if number not in solved_numbers:
                counts[current_status] += 1
            if status is None or current_status == status:
                entries.append({**event, "status": current_status})
        counts["solved"] = len(solved_numbers)
        return {"counts": counts, "entries": entries[:limit]}
