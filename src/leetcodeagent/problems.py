from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Problem:
    number: int
    title: str
    difficulty: str
    topic: str
    slug: str = ""

    @property
    def url(self) -> str | None:
        return f"https://leetcode.com/problems/{self.slug}/" if self.slug else None


rng = np.random.default_rng()


def get_random_problem(
    candidates: list[Problem],
    difficulty: str,
    solved_numbers: set[int],
    topic: str | None = None,
) -> Problem | None:
    """Choose one unsolved LeetCode candidate with NumPy."""
    eligible = [
        problem
        for problem in candidates
        if problem.difficulty == difficulty.lower()
        and problem.number not in solved_numbers
        and (topic is None or topic.casefold() in problem.topic.casefold())
    ]

    if not eligible:
        return None

    index = int(rng.integers(len(eligible)))
    return eligible[index]
