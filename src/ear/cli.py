"""EAR CLI — Typer-based command-line interface."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any

import typer

from ear.config import get_config
from ear.demo_server import serve_demo_api
from ear.fallback import AllCandidatesExhausted
from ear.metrics import get_metrics_collector
from ear.models import BudgetPriority, RouteMetric, RoutingRequest, TaskType
from ear.orchestrator import ExecutionOrchestrator, GuardrailsBlockedError
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
    execute: bool = typer.Option(
        False,
        "--execute",
        "-e",
        help="Execute the prompt against the selected model and display the response.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output result as JSON for scripting pipelines.",
    ),
) -> None:
    """Route a prompt to the best available model and optionally execute it."""
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

    if execute:
        orchestrator = ExecutionOrchestrator.from_config(config)
        try:
            result = asyncio.run(orchestrator.run(request, models))
        except GuardrailsBlockedError as exc:
            typer.echo(f"Blocked by guardrails: {exc.reason}", err=True)
            raise typer.Exit(code=1) from exc
        except AllCandidatesExhausted as exc:
            typer.echo(f"All candidates exhausted: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        payload: dict[str, Any] = {
            "selected_model": result.response.model,
            "task_type": result.decision.task_type.value,
            "budget_priority": budget.value,
            "suitability_score": result.decision.suitability_score,
            "fallback_chain": result.decision.fallback_chain,
            "fallback_trace": result.fallback_trace,
            "reason": result.decision.reason,
            "response_text": result.response.content,
            "prompt_tokens": result.response.prompt_tokens,
            "completion_tokens": result.response.completion_tokens,
            "total_tokens": result.response.total_tokens,
            "estimated_cost_usd": result.estimated_cost_usd,
            "end_to_end_latency_ms": result.end_to_end_latency_ms,
        }

        if json_output:
            typer.echo(json.dumps(payload, indent=2, sort_keys=True))
            return

        typer.echo(f"Selected model : {result.response.model}")
        typer.echo(f"Task type      : {result.decision.task_type.value}")
        typer.echo(f"Budget         : {budget.value}")
        typer.echo(f"Score          : {result.decision.suitability_score:.6f}")
        typer.echo(f"Fallback chain : {', '.join(result.decision.fallback_chain) if result.decision.fallback_chain else '(none)'}")
        typer.echo(f"Fallback trace : {', '.join(result.fallback_trace)}")
        typer.echo(f"Reason         : {result.decision.reason}")
        typer.echo(f"Tokens         : prompt={result.response.prompt_tokens} completion={result.response.completion_tokens}")
        typer.echo(f"Est. cost USD  : {result.estimated_cost_usd:.8f}")
        typer.echo(f"Latency ms     : {result.end_to_end_latency_ms:.3f}")
        typer.echo("")
        typer.echo("--- Response ---")
        typer.echo(result.response.content)
        return

    router = RouterEngine()
    started = time.perf_counter()
    try:
        decision = router.decide(request, models)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    # Route-only mode — no real model call; cost is zero.
    get_metrics_collector().record(
        RouteMetric(
            model_id=decision.selected_model,
            latency_ms=elapsed_ms,
            estimated_cost_usd=0.0,
            task_type=decision.task_type,
            success=True,
        )
    )

    payload = {
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


# Short alias: `ear r "prompt"`
app.command(name="r", hidden=True)(route)


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


# Short aliases: `ear models` / `ear im`
app.command(name="models", hidden=True)(inspect_models)
app.command(name="im", hidden=True)(inspect_models)


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


# Short alias: `ear s`
app.command(name="s", hidden=True)(stats)


@app.command(name="demo-server")
def demo_server(
    host: str = typer.Option("127.0.0.1", help="Host interface to bind the demo API server."),
    port: int = typer.Option(8085, min=1, max=65535, help="TCP port for the demo API server."),
) -> None:
    """Start the local EAR demo backend API server."""
    typer.echo(f"Starting EAR demo API on http://{host}:{port}")
    serve_demo_api(host=host, port=port)


# Short alias: `ear demo`
app.command(name="demo", hidden=True)(demo_server)


# All registered subcommand names (including aliases). Used to detect when
# the user types a bare prompt without an explicit subcommand so we can
# default to `route`.
_SUBCOMMANDS: frozenset[str] = frozenset({
    "route", "r",
    "inspect-models", "models", "im",
    "stats", "s",
    "demo-server", "demo",
})


def main() -> None:
    """Entry point for the ear CLI.

    If the first argument is not a known subcommand (and not a flag), it is
    treated as a prompt and forwarded to the ``route`` command automatically,
    so ``ear "my prompt"`` is equivalent to ``ear route "my prompt"``.
    """
    if (
        len(sys.argv) > 1
        and sys.argv[1] not in _SUBCOMMANDS
        and not sys.argv[1].startswith("-")
    ):
        sys.argv.insert(1, "route")
    app()


if __name__ == "__main__":
    main()
