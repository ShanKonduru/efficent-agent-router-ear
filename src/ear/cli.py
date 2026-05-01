"""EAR CLI — Typer-based command-line interface."""
from __future__ import annotations

import json
import sys

import typer

from ear.config import get_config
from ear.models import BudgetPriority, TaskType

app = typer.Typer(
    name="ear",
    help="Efficient Agent Router — routes prompts to the best LLM.",
    add_completion=False,
)


@app.command()
def route(
    prompt: str = typer.Argument(..., help="The prompt to route and execute."),
    task: TaskType | None = typer.Option(
        None,
        "--task",
        "-t",
        help="Task type hint: simple | planning | coding | research.",
    ),
    budget: BudgetPriority = typer.Option(
        BudgetPriority.MEDIUM,
        "--budget",
        "-b",
        help="Budget priority: low | medium | high.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output result as JSON for scripting pipelines.",
    ),
) -> None:
    """Route a prompt to the best available model and execute it."""
    raise NotImplementedError


@app.command(name="inspect-models")
def inspect_models(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output model list as JSON.",
    ),
) -> None:
    """List all available models with context size and pricing."""
    raise NotImplementedError


@app.command()
def stats(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output session stats as JSON.",
    ),
) -> None:
    """Display cost and latency metrics for the current session."""
    raise NotImplementedError


def main() -> None:
    """Entry point for the ear CLI."""
    app()


if __name__ == "__main__":
    main()
