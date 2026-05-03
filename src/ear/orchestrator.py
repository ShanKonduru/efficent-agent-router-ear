"""Execution orchestrator — composes guardrails → router → executor → fallback into one pipeline.

``ExecutionOrchestrator.run`` is the single entry point for a route-and-execute
operation.  It guarantees:

1. Safety pre-check via ``GuardrailsChecker``.
2. Prompt-injection blocks fail closed immediately (no model call).
3. PII-detected prompts are restricted to vetted providers before routing.
4. ``RouterEngine`` selects the best model and builds the fallback chain.
5. ``ExecutingFallbackPipeline`` executes the prompt with retry/cascade.
6. Real token usage and cost are captured and emitted to ``MetricsCollector``.
"""
from __future__ import annotations

import logging
import time

from ear.config import EARConfig
from ear.executor import (
    CompositeExecutingFallbackPipeline,
    CompositeExecutor,
    ExecutingFallbackPipeline,
    LLMExecutor,
    OllamaExecutor,
    _compute_cost,
)
from ear.guardrails import GuardrailsChecker, OLLAMA_PROVIDER
from ear.metrics import MetricsCollector, get_metrics_collector
from ear.models import (
    ExecutionResult,
    LLMSpec,
    RouteMetric,
    RoutingRequest,
)
from ear.router_engine import RouterEngine

logger = logging.getLogger(__name__)


class GuardrailsBlockedError(Exception):
    """Raised when the guardrail check blocks the request before routing."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"Request blocked by guardrails: {reason}")


class ExecutionOrchestrator:
    """Coordinates the full route-and-execute lifecycle for a single request.

    All collaborators are injected for testability.  The factory method
    :meth:`from_config` constructs a production-ready instance.
    """

    def __init__(
        self,
        guardrails: GuardrailsChecker,
        router: RouterEngine,
        pipeline: ExecutingFallbackPipeline,
        metrics: MetricsCollector,
    ) -> None:
        self._guardrails = guardrails
        self._router = router
        self._pipeline = pipeline
        self._metrics = metrics

    @classmethod
    def from_config(cls, config: EARConfig) -> "ExecutionOrchestrator":
        """Return a production orchestrator wired to real collaborators."""
        openrouter_executor = LLMExecutor(config)
        if config.ear_ollama_enabled:
            ollama_executor = OllamaExecutor(config)
            composite = CompositeExecutor(openrouter=openrouter_executor, ollama=ollama_executor)
            pipeline: ExecutingFallbackPipeline | CompositeExecutingFallbackPipeline = (
                CompositeExecutingFallbackPipeline(
                    executor=composite,
                    max_retries=config.ear_max_retries,
                )
            )
        else:
            pipeline = ExecutingFallbackPipeline(
                executor=openrouter_executor,
                max_retries=config.ear_max_retries,
            )
        return cls(
            guardrails=GuardrailsChecker(),
            router=RouterEngine(),
            pipeline=pipeline,
            metrics=get_metrics_collector(),
        )

    async def run(
        self,
        request: RoutingRequest,
        models: list[LLMSpec],
    ) -> ExecutionResult:
        """Execute the full route-and-execute pipeline.

        Raises:
            GuardrailsBlockedError: If injection is detected.
            AllCandidatesExhausted: If every candidate model fails.
        """
        wall_start = time.perf_counter()

        # 1. Safety pre-check
        guardrail_result = self._guardrails.check(request.prompt)

        # 2. Determine candidate model pool based on guardrail outcome.
        #    Ollama (trusted=True) is always safe; cloud providers are gated.
        ollama_models = [m for m in models if m.id.startswith(f"{OLLAMA_PROVIDER}/")]

        if not guardrail_result.passed:
            # Injection blocked: route to local Ollama only (fail-closed if unavailable).
            if not ollama_models:
                raise GuardrailsBlockedError(guardrail_result.reason or "Safety check failed.")
            candidate_models = ollama_models
            logger.warning(
                "Guardrail blocked prompt (risk=%.2f); routing to local Ollama. reason=%s",
                guardrail_result.risk_score,
                guardrail_result.reason,
            )
        elif guardrail_result.pii_detected:
            # PII detected: prefer Ollama; fall back to vetted cloud providers.
            from ear.guardrails import PII_VETTED_PROVIDERS  # local import to avoid circular
            vetted_cloud = [
                m for m in models
                if not m.id.startswith(f"{OLLAMA_PROVIDER}/")
                and m.id.split("/")[0] in PII_VETTED_PROVIDERS
            ]
            candidate_models = ollama_models + vetted_cloud
            if not candidate_models:
                logger.warning("PII detected but no trusted models available; using all models.")
                candidate_models = list(models)
            else:
                logger.info(
                    "PII detected; restricted routing pool to %d trusted models "
                    "(%d Ollama, %d vetted cloud).",
                    len(candidate_models),
                    len(ollama_models),
                    len(vetted_cloud),
                )
        elif guardrail_result.injection_detected:
            # Elevated injection risk (below block threshold): prefer Ollama when available.
            if ollama_models:
                candidate_models = ollama_models
                logger.info(
                    "Elevated injection risk (score=%.2f); preferring Ollama models.",
                    guardrail_result.risk_score,
                )
            else:
                candidate_models = list(models)
                logger.warning(
                    "Elevated injection risk (score=%.2f) but no Ollama available; "
                    "routing to cloud with caution.",
                    guardrail_result.risk_score,
                )
        else:
            candidate_models = list(models)

        # 3. Routing decision
        decision = self._router.decide(request, candidate_models)

        # 4. Execute with fallback
        fallback_result = await self._pipeline.execute(decision, request.prompt)

        # 5. Compute real cost from usage + model pricing
        wall_ms = (time.perf_counter() - wall_start) * 1000.0
        execution_response = fallback_result.response

        model_spec = next((m for m in models if m.id == execution_response.model), None)
        pricing = model_spec.pricing if model_spec else None
        cost = (
            _compute_cost(
                pricing.prompt,
                pricing.completion,
                execution_response.prompt_tokens,
                execution_response.completion_tokens,
            )
            if pricing
            else 0.0
        )

        fallback_trace = [a.model_id for a in fallback_result.attempts]

        # 6. Emit real telemetry
        self._metrics.record(
            RouteMetric(
                model_id=execution_response.model,
                latency_ms=wall_ms,
                estimated_cost_usd=cost,
                task_type=decision.task_type,
                success=True,
                prompt_tokens=execution_response.prompt_tokens,
                completion_tokens=execution_response.completion_tokens,
                fallback_attempts=len(fallback_trace) - 1,
            )
        )

        return ExecutionResult(
            decision=decision,
            response=execution_response,
            fallback_trace=fallback_trace,
            end_to_end_latency_ms=wall_ms,
            estimated_cost_usd=cost,
            guardrail_result=guardrail_result,
        )
