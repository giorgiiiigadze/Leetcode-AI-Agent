import re

from .agent import LeetcodeAgent
from .config import settings

from rich.console import Console
from rich.prompt import Confirm, Prompt

EXIT_COMMANDS = {"exit", "quit", "q"}

console = Console()

def _wants_problem_recommendation(question: str) -> bool:
    """Recognize requests to pick a LeetCode practice problem."""
    if not re.search(r"\b(problems?|questions?)\b", question, re.IGNORECASE):
        return False
    if re.search(r"\b(solved|completed|history|progress|stats|review)\b", question, re.IGNORECASE):
        return False
    return bool(
        re.search(
            r"\b(random|recommend|suggest|pick|choose|practice|give|show|find|want|need)\b",
            question,
            re.IGNORECASE,
        )
    )


def main() -> None:
    """Start an interactive terminal chat with the LeetCode coach."""
    status = console.status("[bold cyan]Thinking...", spinner="dots")

    def confirm_delete(entry: str) -> bool:
        """Require a terminal user's explicit approval before deleting memory."""
        status.stop()
        try:
            return Confirm.ask(
                f'Delete memory "{entry}"?',
                console=console,
                default=True,
            )
        except EOFError:
            return False
        finally:
            status.start()

    agent = LeetcodeAgent(settings, confirm_delete=confirm_delete)
    console.print(f"LeetCode Coach ({settings.model}) — Ctrl+C to quit")

    while True:
        try:
            question = console.input("\n[bold]You:[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nBye!")
            return

        if not question:
            continue
        if question.lower() in EXIT_COMMANDS:
            console.print("Bye!")
            return

        try:
            if _wants_problem_recommendation(question):
                difficulty = Prompt.ask(
                    "[bold cyan]Choose difficulty[/bold cyan]",
                    choices=["easy", "medium", "hard"],
                    case_sensitive=False,
                    console=console,
                )
                question = (
                    f"{question}\n\nDifficulty selected in the menu: {difficulty}. "
                    "Recommend one random problem at this difficulty."
                )

            with status:
                answer = agent.ask(question)
            console.print("\n[bold green]Coach:[/]", answer)
        except (EOFError, KeyboardInterrupt):
            console.print("\nBye!")
            return
        except Exception as error:
            console.print(f"\nCoach: I couldn't answer that: {error}\n")
