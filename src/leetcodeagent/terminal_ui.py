"""Terminal input and display helpers for code-heavy conversations."""

from __future__ import annotations

import re

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax


CODE_BLOCK = re.compile(r"(?ms)^```([^\n]*)\n(.*?)^```[ \t]*(?=\n|$)")


def print_code_panel(output: Console, code: str, language: str = "python", *, title: str = "Code") -> None:
    """Show code separately from the surrounding chat text."""
    syntax = Syntax(
        code.rstrip("\n"),
        language or "text",
        line_numbers=code.count("\n") >= 4,
        word_wrap=True,
        background_color="default",
    )
    output.print(Panel(syntax, title=title, border_style="cyan"))


def print_coach_answer(output: Console, answer: str) -> None:
    """Render fenced code in panels while leaving normal prose as chat text."""
    output.print("\n[bold green]Coach:[/]")
    position = 0
    for match in CODE_BLOCK.finditer(answer):
        prose = answer[position:match.start()].strip("\n")
        if prose:
            output.print(prose, markup=False)
        language = match.group(1).strip().split(maxsplit=1)[0] if match.group(1).strip() else "text"
        print_code_panel(output, match.group(2), language, title=language.title())
        position = match.end()
    remaining = answer[position:].strip("\n")
    if remaining:
        output.print(remaining, markup=False)


def read_user_message(output: Console) -> str:
    """Read a chat turn, including optional multi-line pasted code."""
    first_line = output.input("\n[bold]You:[/] ").strip()
    if first_line.startswith("/paste") and (first_line == "/paste" or first_line[6:7].isspace()):
        question = first_line[6:].strip() or "Please explain this code."
        output.print("Paste your code below. Enter [bold]/end[/] on its own line when finished.")
        lines = []
        while True:
            line = output.input()
            if line.strip() == "/end":
                break
            lines.append(line)
        code = "\n".join(lines).rstrip()
        if not code:
            return ""
        print_code_panel(output, code, title="Your code")
        return f"{question}\n\n```python\n{code}\n```"

    if first_line.startswith("```"):
        lines = [first_line]
        while True:
            line = output.input()
            lines.append(line)
            if line.strip() == "```":
                break
        message = "\n".join(lines)
        match = CODE_BLOCK.search(message)
        if match:
            language = match.group(1).strip() or "text"
            print_code_panel(output, match.group(2), language, title="Your code")
        return message

    return first_line
