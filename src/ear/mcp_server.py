"""EAR MCP Server — exposes routing engine as an MCP tool and resource.

Phase 2: implemented after CLI validation is complete.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from ear.config import get_config
from ear.fallback import AllCandidatesExhausted
from ear.metrics import get_metrics_collector
from ear.models import BudgetPriority, RouteMetric, RoutingRequest
from ear.orchestrator import ExecutionOrchestrator, GuardrailsBlockedError
from ear.registry import RegistryFactory
from ear.router_engine import RouterEngine

logger = logging.getLogger(__name__)


class RouteAndExecuteInput(BaseModel):
    """Input payload for the `route_and_execute` MCP tool."""

    task_description: str = Field(..., min_length=1)
    budget_priority: BudgetPriority = Field(default=BudgetPriority.MEDIUM)
    execute: bool = Field(default=False, description="When True, execute the prompt against the selected model.")


class EARMCPService:
    """Service layer used by MCP handlers."""

    async def route_and_execute(
        self,
        task_description: str,
        budget_priority: BudgetPriority = BudgetPriority.MEDIUM,
        execute: bool = False,
    ) -> dict[str, Any]:
        """Route a task and optionally execute it against the selected model."""
        request_input = RouteAndExecuteInput(
            task_description=task_description,
            budget_priority=budget_priority,
            execute=execute,
        )

        config = get_config()
        registry = RegistryFactory.create(config)
        models = await registry.get_models()

        request = RoutingRequest(
            prompt=request_input.task_description,
            budget_priority=request_input.budget_priority,
        )

        if request_input.execute:
            orchestrator = ExecutionOrchestrator.from_config(config)
            try:
                result = await orchestrator.run(request, models)
            except GuardrailsBlockedError as exc:
                return {"error": "guardrails_blocked", "reason": exc.reason}
            except AllCandidatesExhausted as exc:
                return {"error": "all_candidates_exhausted", "reason": str(exc)}

            return {
                "selected_model": result.response.model,
                "fallback_chain": result.decision.fallback_chain,
                "fallback_trace": result.fallback_trace,
                "task_type": result.decision.task_type.value,
                "suitability_score": result.decision.suitability_score,
                "reason": result.decision.reason,
                "response_text": result.response.content,
                "prompt_tokens": result.response.prompt_tokens,
                "completion_tokens": result.response.completion_tokens,
                "total_tokens": result.response.total_tokens,
                "estimated_cost_usd": result.estimated_cost_usd,
                "end_to_end_latency_ms": result.end_to_end_latency_ms,
            }

        started = time.perf_counter()
        decision = RouterEngine().decide(request, models)
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        get_metrics_collector().record(
            RouteMetric(
                model_id=decision.selected_model,
                latency_ms=elapsed_ms,
                estimated_cost_usd=0.0,
                task_type=decision.task_type,
                success=True,
            )
        )

        return {
            "selected_model": decision.selected_model,
            "fallback_chain": decision.fallback_chain,
            "task_type": decision.task_type.value,
            "suitability_score": decision.suitability_score,
            "reason": decision.reason,
        }

    def model_stats(self) -> dict[str, Any]:
        """Return the current session summary."""
        return get_metrics_collector().summary().model_dump(mode="json")


def _build_server(service: EARMCPService | None = None) -> FastMCP:
    """Create and configure the FastMCP server instance."""
    mcp = FastMCP("ear")
    svc = service or EARMCPService()

    @mcp.tool(
        name="route_and_execute",
        description=(
            "Route a task description to the most suitable model and optionally execute it. "
            "Set execute=True to perform a real model call and receive response_text."
        ),
    )
    async def route_and_execute(
        task_description: str,
        budget_priority: BudgetPriority = BudgetPriority.MEDIUM,
        execute: bool = False,
    ) -> dict[str, Any]:
        return await svc.route_and_execute(task_description, budget_priority, execute)

    @mcp.resource(
        "ear://session/stats",
        name="session_stats",
        description="Current EAR session routing statistics.",
        mime_type="application/json",
    )
    def session_stats() -> str:
        return json.dumps(svc.model_stats(), sort_keys=True)

    return mcp


async def serve() -> None:
    """Start the EAR MCP server (stdio transport).

    Implementation deferred to Phase 2 (M4).
    Reuses RouterEngine and RegistryClient from the core layer.
    """
    logger.info("Starting EAR MCP server over stdio transport.")
    _build_server().run(transport="stdio")
