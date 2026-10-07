from .agent import LeetcodeAgent
from .config import settings

from rich.console import Console
# from rich.markdown import Markdown
from rich.prompt import Confirm

EXIT_COMMANDS = {"exit", "quit", "q"}

console = Console()


# def _print_coach_answer(answer: str, output: Console = console) -> None:
#     """Render the model's Markdown formatting in the terminal."""
#     output.print("\n[bold green]Coach:[/]")
#     output.print(Markdown(answer))


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
            with status:
                answer = agent.ask(question)
            # _print_coach_answer(answer)
            console.print("\n[bold green]Coach:[/]", answer)
        except (EOFError, KeyboardInterrupt):
            console.print("\nBye!")
            return
        except Exception as error:
            console.print(f"\nCoach: I couldn't answer that: {error}\n")
