"""EAR CLI — Typer-based command-line interface."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any

import typer

from ear.config import get_config
from ear.metrics import get_metrics_collector
from ear.models import BudgetPriority, RouteMetric, RoutingRequest, TaskType
from ear.registry import RegistryFactory
from ear.router_engine import RouterEngine

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
    if not prompt.strip():
        typer.echo("Error: prompt must not be empty.", err=True)
        raise typer.Exit(code=1)

    try:
        request = RoutingRequest(
            prompt=prompt,
            task_type=task,
            budget_priority=budget,
        )
    except Exception as exc:  # pragma: no cover - defensive validation path
        typer.echo(f"Invalid request: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    config = get_config()
    registry = RegistryFactory.create(config)

    try:
        models = asyncio.run(registry.get_models())
    except Exception as exc:
        typer.echo(f"Failed to load model registry: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if not models:
        typer.echo("No models available from registry.", err=True)
        raise typer.Exit(code=1)

    router = RouterEngine()
    started = time.perf_counter()
    try:
        decision = router.decide(request, models)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    # For now, route computes decision only; cost estimation is a placeholder.
    get_metrics_collector().record(
        RouteMetric(
            model_id=decision.selected_model,
            latency_ms=elapsed_ms,
            estimated_cost_usd=0.0,
            task_type=decision.task_type,
            success=True,
        )
    )

    payload: dict[str, Any] = {
        "selected_model": decision.selected_model,
        "task_type": decision.task_type.value,
        "budget_priority": budget.value,
        "suitability_score": decision.suitability_score,
        "fallback_chain": decision.fallback_chain,
        "reason": decision.reason,
    }

    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    typer.echo(f"Selected model : {decision.selected_model}")
    typer.echo(f"Task type      : {decision.task_type.value}")
    typer.echo(f"Budget         : {budget.value}")
    typer.echo(f"Score          : {decision.suitability_score:.6f}")
    typer.echo(f"Fallback chain : {', '.join(decision.fallback_chain) if decision.fallback_chain else '(none)'}")
    typer.echo(f"Reason         : {decision.reason}")


@app.command(name="inspect-models")
def inspect_models(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output model list as JSON.",
    ),
) -> None:
    """List all available models with context size and pricing."""
    config = get_config()
    registry = RegistryFactory.create(config)

    try:
        models = asyncio.run(registry.get_models())
    except Exception as exc:
        typer.echo(f"Failed to load model registry: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if json_output:
        typer.echo(
            json.dumps([model.model_dump(mode="json") for model in models], indent=2, sort_keys=True)
        )
        return

    if not models:
        typer.echo("No models available from registry.")
        return

    for model in models:
        if model.pricing is None:
            pricing = "n/a"
        else:
            pricing = f"prompt={model.pricing.prompt:.8f}, completion={model.pricing.completion:.8f}"
        typer.echo(
            f"{model.id} | context={model.context_length} | pricing={pricing}"
        )


@app.command()
def stats(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output session stats as JSON.",
    ),
) -> None:
    """Display cost and latency metrics for the current session."""
    summary = get_metrics_collector().summary()

    if json_output:
        typer.echo(json.dumps(summary.model_dump(mode="json"), indent=2, sort_keys=True))
        return

    typer.echo(f"Total calls    : {summary.total_calls}")
    typer.echo(f"Total cost USD : {summary.total_cost_usd:.6f}")
    typer.echo(f"Total latency  : {summary.total_latency_ms:.3f} ms")
    if summary.calls_by_model:
        typer.echo("Calls by model :")
        for model_id, count in sorted(summary.calls_by_model.items()):
            typer.echo(f"  - {model_id}: {count}")


def main() -> None:
    """Entry point for the ear CLI."""
    app()


if __name__ == "__main__":
    main()
