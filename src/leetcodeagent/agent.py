from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from openai import OpenAI

from collections.abc import Callable

from .config import DEFAULT_MEMORY_PATH, Settings
from .memory import MemoryStore
from .prompts import SYSTEM_PROMPT


class LeetcodeAgent:
    """Answer LeetCode questions with the user's Markdown memory as context."""

    def __init__(
        self,
        settings: Settings,
        *,
        confirm_delete: Callable[[str], bool],
        memory_path: Path = DEFAULT_MEMORY_PATH,
        client: Any | None = None,
    ) -> None:
        self.client = client or OpenAI(api_key=settings.api_key)
        self.model = settings.model
        self.memory = MemoryStore(memory_path)
        self.confirm_delete = confirm_delete
        self.previous_response_id: str | None = None
        self.last_recommended_problem: str | None = None

    def ask(self, question: str) -> str:
        """Answer one question using the latest contents of ``memory.md``."""
        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValueError("Please ask a LeetCode question.")

        if re.fullmatch(
            r"(?:i\s+)?(?:solved|finished|completed|did)\s+(?:that|it|this)(?:\s+(?:one|problem))?[.!]?",
            cleaned_question,
            re.IGNORECASE,
        ) and self.last_recommended_problem:
            entry = self.last_recommended_problem
            if f"- {entry}" in self.memory.read().splitlines():
                return f"{entry} is already in memory.md."
            self.memory.save(entry)
            return f"Saved {entry} to memory.md."

        response = self.client.responses.create(
            model=self.model,
            instructions=SYSTEM_PROMPT,
            input=self._build_input(cleaned_question),
            previous_response_id=self.previous_response_id,
            tools=self._tools(),
            reasoning={"effort": "none"},
        )

        while function_calls := [
            item for item in response.output if item.type == "function_call"
        ]:
            tool_outputs = [
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": self._run_tool(call.name, call.arguments),
                }
                for call in function_calls
            ]

            response = self.client.responses.create(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                input=tool_outputs,
                previous_response_id=response.id,
                tools=self._tools(),
                reasoning={"effort": "none"},
            )

        answer = response.output_text.strip()
        if not answer:
            raise RuntimeError("The model returned no text response.")
        self.previous_response_id = response.id
        if re.search(r"\b(random|recommend|suggest)\b", cleaned_question, re.IGNORECASE):
            recommendation = re.search(
                r"\b([1-9]\d*)\.\s+([A-Za-z][^\n—–]+?)\s*[—–]",
                answer,
            )
            self.last_recommended_problem = (
                f"{recommendation.group(1)}. {recommendation.group(2).strip(' *')}"
                if recommendation
                else None
            )
        return answer

    def _build_input(self, question: str) -> str:
        return f"""Current contents of memory.md:
                ---
                {self.memory.read()}
                ---

                User question: {question}
            """

    def _run_tool(self, name: str, raw_arguments: str) -> str:
        """Run the one local action the model is permitted to request."""
        if name not in {"save_memory", "save_memories", "delete_memory"}:
            return json.dumps({"error": f"Unknown tool: {name}"})

        try:
            arguments = json.loads(raw_arguments or "{}")
        except json.JSONDecodeError:
            return json.dumps({"error": "Tool arguments must be valid JSON."})

        if not isinstance(arguments, dict):
            return json.dumps({"error": "Tool arguments must be an object."})

        try:
            if name == "save_memories":
                entries = arguments.get("entries")
                if not isinstance(entries, list) or not all(
                    isinstance(entry, str) and entry.strip() for entry in entries
                ):
                    return json.dumps(
                        {"error": "save_memories requires a nonempty list of entries."}
                    )
                saved_entries = self.memory.save_many(entries)
                return json.dumps({"message": "Memories saved.", "entries": saved_entries})

            entry = arguments.get("entry")
            if not isinstance(entry, str) or not entry.strip():
                return json.dumps({"error": f"{name} requires a nonempty entry."})

            if name == "save_memory":
                saved_entry = self.memory.save(entry)
                return json.dumps({"message": "Memory saved.", "entry": saved_entry})

            if not self.confirm_delete(entry):
                return json.dumps(
                    {"message": "Memory deletion was cancelled by the user.", "entry": entry}
                )

            deleted = self.memory.delete(entry)

            if not deleted:
                return json.dumps({"error": "No exact matching memory entry was found."})
            return json.dumps({"message": "Memory deleted.", "entry": entry.strip()})
        except ValueError as error:
            return json.dumps({"error": str(error)})

    @staticmethod
    def _tools() -> list[dict[str, Any]]:
        """Return the narrow local tool available to the model."""
        return [
            {
                "type": "function",
                "name": "save_memory",
                "description": (
                    "Save one solved LeetCode problem to memory.md as its number and title, "
                    "for example '1. Two Sum'. Do not guess an unknown number."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entry": {
                            "type": "string",
                            "description": "LeetCode number and exact title, e.g. '1. Two Sum'. No bullet prefix.",
                        }
                    },
                    "required": ["entry"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
            {
                "type": "function",
                "name": "save_memories",
                "description": (
                    "Save several solved LeetCode problems to memory.md, each as a "
                    "number and title. Do not guess unknown numbers."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entries": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "description": "One number and exact title per entry, e.g. '1. Two Sum'.",
                        }
                    },
                    "required": ["entries"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
            {
                "type": "function",
                "name": "delete_memory",
                "description": (
                    "Delete one exact memory.md entry. Use only when the user explicitly "
                    "asks to remove a specific saved memory."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entry": {
                            "type": "string",
                            "description": "The exact memory entry to delete, without a bullet prefix.",
                        }
                    },
                    "required": ["entry"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        ]


# Kept as a conventional spelling for callers that prefer it.
LeetCodeAgent = LeetcodeAgent
