"""Persistent storage for the LeetCode coach's Markdown memory."""

from pathlib import Path
import re


class MemoryStore:
    """Read and make small, exact changes to one ``memory.md`` file."""

    # Defining the path to the memory.md file
    def __init__(self, path: Path) -> None:
        self.path = path

    # Defining the read function, to read the current memory.md file
    def read(self) -> str:
        """Return the memory contents, including a helpful empty-state message."""
        if not self.path.exists():
            return "(memory.md does not exist yet.)"

        contents = self.path.read_text(encoding="utf-8").strip()
        return contents or "(memory.md is currently empty.)"

    # Defining the save function to save memory in memory.md file
    def save(self, entry: str) -> str:
        """Append one concise bullet entry and return the saved text."""
        cleaned_entry = self._clean_problem_entry(entry)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with self.path.open("a", encoding="utf-8") as memory_file:
            if self.path.stat().st_size:
                memory_file.write("\n")
            memory_file.write(f"- {cleaned_entry}\n")

        return cleaned_entry

    def save_many(self, entries: list[str]) -> list[str]:
        """Append several memory entries together and return their clean text."""
        cleaned_entries = [self._clean_problem_entry(entry) for entry in entries]
        if not cleaned_entries:
            raise ValueError("Provide at least one memory entry.")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as memory_file:
            if self.path.stat().st_size:
                memory_file.write("\n")
            memory_file.write("\n".join(f"- {entry}" for entry in cleaned_entries))
            memory_file.write("\n")

        return cleaned_entries

    def delete(self, entry: str) -> bool:
        """Remove one exactly matching bullet entry, if it exists."""
        cleaned_entry = self._clean_entry(entry)
        if not self.path.exists():
            return False

        target = f"- {cleaned_entry}"
        lines = self.path.read_text(encoding="utf-8").splitlines()
        try:
            lines.remove(target)
        except ValueError:
            return False

        contents = "\n".join(lines).strip()
        self.path.write_text(f"{contents}\n" if contents else "", encoding="utf-8")
        return True

    @staticmethod
    def _clean_entry(entry: str) -> str:
        """Validate an entry and avoid duplicate Markdown bullet prefixes."""
        cleaned_entry = entry.strip().removeprefix("- ").strip()
        if not cleaned_entry:
            raise ValueError("A memory entry cannot be empty.")
        return cleaned_entry

    @classmethod
    def _clean_problem_entry(cls, entry: str) -> str:
        """Require a LeetCode number followed by its problem title for new saves."""
        cleaned_entry = cls._clean_entry(entry)
        if not re.fullmatch(r"[1-9]\d*\. [^\n]+", cleaned_entry):
            raise ValueError("Use a LeetCode number and title, like '1. Two Sum'.")
        return cleaned_entry
