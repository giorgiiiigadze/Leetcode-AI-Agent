from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from collections.abc import Callable

from .config import DEFAULT_MEMORY_PATH, Settings
from .memory import MemoryStore
from .leetcode_client import LeetCodeClient
from .prompts import SYSTEM_PROMPT
from .problems import Problem, get_random_problem

class LeetcodeAgent:
    """Answer LeetCode questions with the user's Markdown memory as context."""

    def __init__(
        self,
        settings: Settings,
        *,
        confirm_delete: Callable[[str], bool],
        memory_path: Path = DEFAULT_MEMORY_PATH,
        client: Any | None = None,
        leetcode_client: LeetCodeClient | None = None,
    ) -> None:
        self.client = client or OpenAI(api_key=settings.api_key)
        self.model = settings.model
        self.memory = MemoryStore(memory_path)
        self.leetcode_client = leetcode_client or LeetCodeClient()
        self.confirm_delete = confirm_delete
        self.previous_response_id: str | None = None
        self.last_recommended_problem: str | None = None
        self.last_recommended_problem_details: Problem | None = None

    def get_random_problem(self, difficulty: str, topic: str | None = None) -> Problem | None:
        """Pick a real public LeetCode problem absent from memory.md."""
        difficulty = difficulty.strip().lower()
        if difficulty not in {"easy", "medium", "hard"}:
            raise ValueError("Difficulty must be easy, medium, or hard.")

        solved_numbers = self.memory.solved_numbers()
        if self.last_recommended_problem_details is not None:
            solved_numbers.add(self.last_recommended_problem_details.number)
        candidates = self.leetcode_client.get_candidate_problems(difficulty)
        problem = get_random_problem(candidates, difficulty, solved_numbers, topic)
        if problem is None:
            # Rare filters can miss the sampled page; search the full catalog then.
            candidates = self.leetcode_client.get_problems(difficulty)
            problem = get_random_problem(candidates, difficulty, solved_numbers, topic)
        if problem is not None:
            self.last_recommended_problem = (
                f"{problem.number}. {problem.title} | {problem.difficulty.title()}"
            )
            self.last_recommended_problem_details = problem
        return problem

    def ask(self, question: str) -> str:
        """Answer one question using the latest contents of ``memory.md``."""
        cleaned_question = question.strip()
        if not cleaned_question:
            raise ValueError("Please ask a LeetCode question.")

        response = self.client.responses.create(
            model=self.model,
            instructions=SYSTEM_PROMPT,
            input=self._build_input(cleaned_question),
            previous_response_id=self.previous_response_id,
            tools=self._tools(),
            reasoning={"effort": "none"},
            parallel_tool_calls=False,
        )

        verified_url: str | None = None
        for _ in range(10):
            function_calls = [
                item for item in response.output if item.type == "function_call"
            ]
            if not function_calls:
                break
            tool_outputs = []
            for call in function_calls:
                output = self._run_tool(call.name, call.arguments)
                if call.name in {"get_random_problem", "get_problem_link"}:
                    verified_url = json.loads(output).get("url") or verified_url
                tool_outputs.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": output,
                })

            response = self.client.responses.create(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                input=tool_outputs,
                previous_response_id=response.id,
                tools=self._tools(),
                reasoning={"effort": "none"},
                parallel_tool_calls=False,
            )
        else:
            raise RuntimeError("The agent made too many tool calls in one turn.")

        answer = response.output_text.strip()
        if not answer:
            raise RuntimeError("The model returned no text response.")
        if verified_url and verified_url not in answer:
            answer = f"{answer}\n{verified_url}"
        self.previous_response_id = response.id
        return answer

    def _build_input(self, question: str) -> str:
        return (
            "Current contents of memory.md:\n---\n"
            f"{self.memory.read()}\n"
            "---\n\n"
            f"Most recently recommended problem: {self.last_recommended_problem or 'none'}\n\n"
            f"Last recommendation difficulty: "
            f"{self.last_recommended_problem_details.difficulty if self.last_recommended_problem_details else 'none'}\n\n"
            f"User question: {question}"
        )

    def _run_tool(self, name: str, raw_arguments: str) -> str:
        """Run one of the application's validated tools."""
        if name not in {
            "get_random_problem", "get_problem_link", "mark_solved",
            "save_memory", "save_memories", "delete_memory",
        }:
            return json.dumps({"error": f"Unknown tool: {name}"})

        try:
            arguments = json.loads(raw_arguments or "{}")
        except json.JSONDecodeError:
            return json.dumps({"error": "Tool arguments must be valid JSON."})

        if not isinstance(arguments, dict):
            return json.dumps({"error": "Tool arguments must be an object."})

        try:
            if name == "get_random_problem":
                difficulty = arguments.get("difficulty")
                if difficulty is None:
                    if self.last_recommended_problem_details is not None:
                        difficulty = self.last_recommended_problem_details.difficulty
                    else:
                        return json.dumps({"error": "No difficulty chosen yet. Ask the user whether they want easy, medium, or hard, then call this tool after their reply."})
                if not isinstance(difficulty, str):
                    return json.dumps({"error": "Difficulty must be easy, medium, or hard."})
                topic = arguments.get("topic")
                if topic is not None and not isinstance(topic, str):
                    return json.dumps({"error": "Topic must be text or null."})
                problem = self.get_random_problem(difficulty, topic)
                if problem is None:
                    return json.dumps({"error": "No unsolved problem matched that difficulty and topic."})
                return json.dumps({
                    "number": problem.number,
                    "title": problem.title,
                    "difficulty": problem.difficulty,
                    "topics": problem.topic,
                    "url": problem.url,
                })

            if name == "get_problem_link":
                number = arguments.get("number")
                if number is not None and (type(number) is not int or number <= 0):
                    return json.dumps({"error": "Problem number must be a positive integer or null."})
                problem = self.last_recommended_problem_details
                if number is not None and (problem is None or problem.number != number):
                    problem = None
                    for difficulty in ("easy", "medium", "hard"):
                        problem = next(
                            (item for item in self.leetcode_client.get_problems(difficulty)
                             if item.number == number),
                            None,
                        )
                        if problem is not None:
                            break
                if problem is None or not problem.url:
                    return json.dumps({"error": "No verified link found for that problem."})
                return json.dumps({"number": problem.number, "title": problem.title, "url": problem.url})

            if name == "mark_solved":
                problem = self.last_recommended_problem_details
                if problem is None:
                    return json.dumps({"error": "No recently recommended problem to mark solved."})
                if problem.number in self.memory.solved_numbers():
                    return json.dumps({"message": "Already saved.", "number": problem.number})
                entry = f"{problem.number}. {problem.title} | {problem.difficulty.title()}"
                saved_entry = self.memory.save(entry)
                return json.dumps({"message": "Problem saved as solved.", "entry": saved_entry})

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
        except (ValueError, RuntimeError) as error:
            return json.dumps({"error": str(error)})

    @staticmethod
    def _tools() -> list[dict[str, Any]]:
        """Return application functions the model may call as needed."""
        return [
            {
                "type": "function",
                "name": "get_random_problem",
                "description": (
                    "Fetch and randomly select a real unsolved LeetCode problem. "
                    "Use for requests for a problem, another one, or a replacement after skipping. "
                    "Use null difficulty only to reuse the last recommendation's difficulty. "
                    "If there is no previous recommendation and no requested difficulty, "
                    "ask the user to choose easy, medium, or hard before calling this tool."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "difficulty": {"type": ["string", "null"], "enum": ["easy", "medium", "hard", None]},
                        "topic": {"type": ["string", "null"]},
                    },
                    "required": ["difficulty", "topic"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
            {
                "type": "function",
                "name": "get_problem_link",
                "description": "Get a verified LeetCode URL for the last recommended problem, or a specified problem number.",
                "parameters": {
                    "type": "object",
                    "properties": {"number": {"type": ["integer", "null"]}},
                    "required": ["number"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
            {
                "type": "function",
                "name": "mark_solved",
                "description": "Save the most recently recommended verified problem as solved when the user says they solved it.",
                "parameters": {
                    "type": "object", "properties": {}, "required": [], "additionalProperties": False,
                },
                "strict": True,
            },
            {
                "type": "function",
                "name": "save_memory",
                "description": (
                    "Save one solved LeetCode problem with its number, exact title, "
                    "and difficulty, for example '1. Two Sum | Easy'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entry": {
                            "type": "string",
                            "description": "Number, exact title, and difficulty, e.g. '1. Two Sum | Easy'. No bullet prefix.",
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
                    "Save several solved LeetCode problems, each with number, title, "
                    "and difficulty. Do not guess unknown details."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entries": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "description": "One numbered title and difficulty per entry, e.g. '1. Two Sum | Easy'.",
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
                            "description": "The exact memory entry, including difficulty when present, without a bullet prefix.",
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
