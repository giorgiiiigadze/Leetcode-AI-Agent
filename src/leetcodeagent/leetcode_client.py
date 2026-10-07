"""Fetch public problem metadata from LeetCode's website."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .problems import Problem


GRAPHQL_URL = "https://leetcode.com/graphql/"
PAGE_SIZE = 100
QUESTION_LIST_QUERY = """
query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
  problemsetQuestionList: questionList(
    categorySlug: $categorySlug, limit: $limit, skip: $skip, filters: $filters
  ) {
    total: totalNum
    questions: data {
      frontendQuestionId: questionFrontendId
      title
      titleSlug
      difficulty
      paidOnly: isPaidOnly
      topicTags { name slug }
    }
  }
}
"""


class LeetCodeClient:
    """Read public problems through LeetCode's website GraphQL endpoint.

    This endpoint is not a documented public API and may change.
    """

    def __init__(self, *, timeout: float = 15.0) -> None:
        self.timeout = timeout
        self._cache: dict[str, list[Problem]] = {}

    def get_problems(self, difficulty: str) -> list[Problem]:
        """Return all free problems at one difficulty, cached for this process."""
        difficulty = difficulty.strip().lower()
        if difficulty not in {"easy", "medium", "hard"}:
            raise ValueError("Difficulty must be easy, medium, or hard.")
        if difficulty in self._cache:
            return self._cache[difficulty]

        problems: list[Problem] = []
        skip = 0
        while True:
            payload = self._fetch_page(difficulty, skip)
            try:
                result = payload["data"]["problemsetQuestionList"]
                total = result["total"]
                questions = result["questions"]
            except (KeyError, TypeError) as error:
                raise RuntimeError("LeetCode returned an unexpected problem-list response.") from error
            if not isinstance(total, int) or not isinstance(questions, list):
                raise RuntimeError("LeetCode returned an invalid problem list.")

            for question in questions:
                if not isinstance(question, dict) or question.get("paidOnly"):
                    continue
                try:
                    number = int(question["frontendQuestionId"])
                    title = question["title"]
                    slug = question["titleSlug"]
                    actual_difficulty = question["difficulty"]
                    tags = question["topicTags"]
                except (KeyError, TypeError, ValueError):
                    continue
                if (
                    number <= 0
                    or not isinstance(title, str)
                    or not isinstance(slug, str)
                    or not slug
                    or not isinstance(actual_difficulty, str)
                    or actual_difficulty.lower() != difficulty
                    or not isinstance(tags, list)
                ):
                    continue
                topics = ", ".join(
                    tag["name"]
                    for tag in tags
                    if isinstance(tag, dict) and isinstance(tag.get("name"), str)
                )
                problems.append(Problem(number, title, difficulty, topics or "General", slug))

            skip += len(questions)
            if not questions or skip >= total:
                break

        self._cache[difficulty] = problems
        return problems

    def _fetch_page(self, difficulty: str, skip: int) -> dict:
        body = json.dumps(
            {
                "query": QUESTION_LIST_QUERY,
                "variables": {
                    "categorySlug": "",
                    "skip": skip,
                    "limit": PAGE_SIZE,
                    "filters": {"difficulty": difficulty.upper()},
                },
            }
        ).encode("utf-8")
        request = Request(
            GRAPHQL_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "LeetCodeAgent/0.1",
                "Referer": "https://leetcode.com/problemset/",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Could not fetch LeetCode problems: {error}") from error
        if not isinstance(payload, dict) or payload.get("errors"):
            raise RuntimeError("LeetCode rejected the problem-list request.")
        return payload
