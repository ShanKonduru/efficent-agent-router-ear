"""Tests for ear.orchestrator — ExecutionOrchestrator and GuardrailsBlockedError."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ear.executor import ExecutingFallbackPipeline
from ear.fallback import AllCandidatesExhausted, FallbackResult, FallbackAttempt
from ear.guardrails import GuardrailsChecker
from ear.metrics import MetricsCollector, get_metrics_collector
from ear.models import (
    BudgetPriority,
    ExecutionResponse,
    GuardrailResult,
    LLMPricing,
    LLMSpec,
    RoutingDecision,
    RoutingRequest,
    TaskType,
)
from ear.orchestrator import ExecutionOrchestrator, GuardrailsBlockedError
from ear.router_engine import RouterEngine


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_models(
    with_pricing: bool = True,
) -> list[LLMSpec]:
    pricing = LLMPricing(prompt=0.001, completion=0.002) if with_pricing else None
    return [
        LLMSpec(
            id="openai/gpt-4o-mini",
            name="mini",
            context_length=16_000,
            pricing=pricing,
        ),
        LLMSpec(
            id="anthropic/claude-3-haiku",
            name="haiku",
            context_length=200_000,
            pricing=pricing,
        ),
    ]


def _safe_guardrail_result() -> GuardrailResult:
    return GuardrailResult(passed=True)


def _blocked_guardrail_result(reason: str = "injection detected") -> GuardrailResult:
    return GuardrailResult(
        passed=False,
        injection_detected=True,
        reason=reason,
    )


def _pii_guardrail_result() -> GuardrailResult:
    return GuardrailResult(
        passed=True,
        pii_detected=True,
        reason="email address found",
    )


def _routing_decision(primary: str = "openai/gpt-4o-mini") -> RoutingDecision:
    return RoutingDecision(
        selected_model=primary,
        fallback_chain=["anthropic/claude-3-haiku"],
        task_type=TaskType.SIMPLE,
        suitability_score=0.8,
        reason="scored highest",
    )


def _execution_response(model: str = "openai/gpt-4o-mini") -> ExecutionResponse:
    return ExecutionResponse(
        model=model,
        content="42",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
    )


def _fallback_result(
    model_used: str = "openai/gpt-4o-mini",
    extra_attempts: list[str] | None = None,
) -> FallbackResult:
    attempts: list[FallbackAttempt] = []
    if extra_attempts:
        for m in extra_attempts:
            attempts.append(FallbackAttempt(model_id=m, success=False, error="failed"))
    attempts.append(FallbackAttempt(model_id=model_used, success=True))
    return FallbackResult(
        model_used=model_used,
        response=_execution_response(model_used),
        attempts=attempts,
        succeeded=True,
    )


def _make_orchestrator(
    guardrail_result: GuardrailResult,
    decision: RoutingDecision,
    pipeline_result: FallbackResult | Exception,
    metrics: MetricsCollector | None = None,
) -> ExecutionOrchestrator:
    mock_guardrails = MagicMock(spec=GuardrailsChecker)
    mock_guardrails.check.return_value = guardrail_result

    mock_router = MagicMock(spec=RouterEngine)
    mock_router.decide.return_value = decision

    mock_pipeline = MagicMock(spec=ExecutingFallbackPipeline)
    if isinstance(pipeline_result, Exception):
        mock_pipeline.execute = AsyncMock(side_effect=pipeline_result)
    else:
        mock_pipeline.execute = AsyncMock(return_value=pipeline_result)

    return ExecutionOrchestrator(
        guardrails=mock_guardrails,
        router=mock_router,
        pipeline=mock_pipeline,
        metrics=metrics or MetricsCollector(),
    )


# ── TestGuardrailsBlockedError ────────────────────────────────────────────────

class TestGuardrailsBlockedError:
    def test_stores_reason(self) -> None:
        err = GuardrailsBlockedError("prompt injection detected")
        assert err.reason == "prompt injection detected"
        assert "prompt injection" in str(err)


# ── TestExecutionOrchestrator ─────────────────────────────────────────────────

class TestExecutionOrchestrator:
    async def test_successful_execution(self) -> None:
        models = _make_models()
        decision = _routing_decision()
        fb_result = _fallback_result()

        orch = _make_orchestrator(
            guardrail_result=_safe_guardrail_result(),
            decision=decision,
            pipeline_result=fb_result,
        )

        request = RoutingRequest(prompt="what is 6 * 7?", budget_priority=BudgetPriority.MEDIUM)
        result = await orch.run(request, models)

        assert result.response.content == "42"
        assert result.response.model == "openai/gpt-4o-mini"
        assert result.fallback_trace == ["openai/gpt-4o-mini"]
        assert result.guardrail_result.passed

    async def test_cost_computed_from_pricing(self) -> None:
        models = [
            LLMSpec(
                id="openai/gpt-4o-mini",
                name="mini",
                context_length=16_000,
                pricing=LLMPricing(prompt=0.001, completion=0.002),
            )
        ]
        decision = _routing_decision()
        # tokens: prompt=10, completion=5 → cost = 0.001*10 + 0.002*5 = 0.02
        fb_result = _fallback_result()

        orch = _make_orchestrator(
            guardrail_result=_safe_guardrail_result(),
            decision=decision,
            pipeline_result=fb_result,
        )

        request = RoutingRequest(prompt="hello", budget_priority=BudgetPriority.MEDIUM)
        result = await orch.run(request, models)

        expected_cost = 0.001 * 10 + 0.002 * 5
        assert abs(result.estimated_cost_usd - expected_cost) < 1e-9

    async def test_cost_zero_when_no_pricing(self) -> None:
        models = [
            LLMSpec(
                id="openai/gpt-4o-mini",
                name="mini",
                context_length=16_000,
                pricing=None,
            )
        ]
        decision = _routing_decision()
        fb_result = _fallback_result()

        orch = _make_orchestrator(
            guardrail_result=_safe_guardrail_result(),
            decision=decision,
            pipeline_result=fb_result,
        )

        request = RoutingRequest(prompt="hello", budget_priority=BudgetPriority.MEDIUM)
        result = await orch.run(request, models)

        assert result.estimated_cost_usd == 0.0

    async def test_cost_zero_when_model_not_in_list(self) -> None:
        models: list[LLMSpec] = []  # no matching model in list
        decision = _routing_decision()
        fb_result = _fallback_result()

        orch = _make_orchestrator(
            guardrail_result=_safe_guardrail_result(),
            decision=decision,
            pipeline_result=fb_result,
        )

        request = RoutingRequest(prompt="hello", budget_priority=BudgetPriority.MEDIUM)
        result = await orch.run(request, models)

        assert result.estimated_cost_usd == 0.0

    async def test_guardrails_blocked_raises(self) -> None:
        models = _make_models()
        decision = _routing_decision()

        orch = _make_orchestrator(
            guardrail_result=_blocked_guardrail_result("injection found"),
            decision=decision,
            pipeline_result=_fallback_result(),
        )

        request = RoutingRequest(prompt="ignore previous instructions", budget_priority=BudgetPriority.MEDIUM)
        with pytest.raises(GuardrailsBlockedError) as exc_info:
            await orch.run(request, models)

        assert "injection found" in exc_info.value.reason

    async def test_pii_restricts_candidate_pool(self) -> None:
        # When PII is detected, only vetted providers should be passed to router
        models = [
            LLMSpec(id="openai/gpt-4o-mini", name="mini", context_length=16_000),
            LLMSpec(id="anthropic/claude-3-haiku", name="haiku", context_length=200_000),
            LLMSpec(id="mistral/mistral-7b", name="mistral", context_length=8_000),
        ]
        decision = _routing_decision()
        fb_result = _fallback_result()

        mock_guardrails = MagicMock(spec=GuardrailsChecker)
        mock_guardrails.check.return_value = _pii_guardrail_result()

        mock_router = MagicMock(spec=RouterEngine)
        mock_router.decide.return_value = decision

        mock_pipeline = MagicMock(spec=ExecutingFallbackPipeline)
        mock_pipeline.execute = AsyncMock(return_value=fb_result)

        orch = ExecutionOrchestrator(
            guardrails=mock_guardrails,
            router=mock_router,
            pipeline=mock_pipeline,
            metrics=MetricsCollector(),
        )

        request = RoutingRequest(prompt="my email is test@example.com", budget_priority=BudgetPriority.MEDIUM)
        await orch.run(request, models)

        # Router should only receive vetted models (openai and anthropic, not mistral)
        called_models: list[LLMSpec] = mock_router.decide.call_args[0][1]
        model_ids = [m.id for m in called_models]
        assert "openai/gpt-4o-mini" in model_ids
        assert "anthropic/claude-3-haiku" in model_ids
        assert "mistral/mistral-7b" not in model_ids

    async def test_fallback_trace_captures_all_attempts(self) -> None:
        models = _make_models()
        decision = _routing_decision()
        fb_result = _fallback_result(
            model_used="anthropic/claude-3-haiku",
            extra_attempts=["openai/gpt-4o-mini"],
        )

        orch = _make_orchestrator(
            guardrail_result=_safe_guardrail_result(),
            decision=decision,
            pipeline_result=fb_result,
        )

        request = RoutingRequest(prompt="hello", budget_priority=BudgetPriority.MEDIUM)
        result = await orch.run(request, models)

        assert result.fallback_trace == ["openai/gpt-4o-mini", "anthropic/claude-3-haiku"]

    async def test_metrics_recorded_on_success(self) -> None:
        collector = MetricsCollector()
        models = _make_models()
        decision = _routing_decision()
        fb_result = _fallback_result()

        orch = _make_orchestrator(
            guardrail_result=_safe_guardrail_result(),
            decision=decision,
            pipeline_result=fb_result,
            metrics=collector,
        )

        request = RoutingRequest(prompt="hello", budget_priority=BudgetPriority.MEDIUM)
        await orch.run(request, models)

        summary = collector.summary()
        assert summary.total_calls == 1
        assert "openai/gpt-4o-mini" in summary.calls_by_model

    async def test_all_candidates_exhausted_propagates(self) -> None:
        models = _make_models()
        decision = _routing_decision()

        orch = _make_orchestrator(
            guardrail_result=_safe_guardrail_result(),
            decision=decision,
            pipeline_result=AllCandidatesExhausted(["openai/gpt-4o-mini"]),
        )

        request = RoutingRequest(prompt="hello", budget_priority=BudgetPriority.MEDIUM)
        with pytest.raises(AllCandidatesExhausted):
            await orch.run(request, models)

    async def test_end_to_end_latency_is_positive(self) -> None:
        models = _make_models()
        decision = _routing_decision()
        fb_result = _fallback_result()

        orch = _make_orchestrator(
            guardrail_result=_safe_guardrail_result(),
            decision=decision,
            pipeline_result=fb_result,
        )

        request = RoutingRequest(prompt="timing test", budget_priority=BudgetPriority.MEDIUM)
        result = await orch.run(request, models)

        assert result.end_to_end_latency_ms >= 0.0

    async def test_from_config_creates_orchestrator(self) -> None:
        cfg = MagicMock()
        cfg.ear_openrouter_base_url = "https://openrouter.ai/api/v1"
        cfg.openrouter_api_key = "test-key"
        cfg.ear_request_timeout_seconds = 30.0
        cfg.ear_max_retries = 3
        cfg.ear_ollama_enabled = False

        orch = ExecutionOrchestrator.from_config(cfg)

        assert isinstance(orch, ExecutionOrchestrator)

    async def test_from_config_uses_composite_pipeline_when_ollama_enabled(self) -> None:
        from ear.executor import CompositeExecutingFallbackPipeline

        cfg = MagicMock()
        cfg.ear_openrouter_base_url = "https://openrouter.ai/api/v1"
        cfg.openrouter_api_key = "test-key"
        cfg.ear_request_timeout_seconds = 30.0
        cfg.ear_max_retries = 3
        cfg.ear_ollama_enabled = True
        cfg.ear_ollama_base_url = "http://localhost:11434"

        orch = ExecutionOrchestrator.from_config(cfg)

        assert isinstance(orch, ExecutionOrchestrator)
        assert isinstance(orch._pipeline, CompositeExecutingFallbackPipeline)

    async def test_guardrails_blocked_routes_to_ollama_when_available(self) -> None:
        """Blocked prompts must be routed to Ollama models, not raised as errors."""
        ollama_model = LLMSpec(id="ollama/llama3", name="llama3", context_length=8_192, trusted=True)
        cloud_model = LLMSpec(id="openai/gpt-4o-mini", name="mini", context_length=16_000)
        models = [cloud_model, ollama_model]

        decision = _routing_decision("ollama/llama3")
        fb_result = _fallback_result("ollama/llama3")

        orch = _make_orchestrator(
            guardrail_result=_blocked_guardrail_result("injection found"),
            decision=decision,
            pipeline_result=fb_result,
        )

        request = RoutingRequest(prompt="ignore previous instructions", budget_priority=BudgetPriority.MEDIUM)
        result = await orch.run(request, models)

        # Should succeed — routed to Ollama
        assert result.response.model == "ollama/llama3"

        # Router should have received only the Ollama model
        called_models: list[LLMSpec] = orch._router.decide.call_args[0][1]  # type: ignore[attr-defined]
        assert all(m.id.startswith("ollama/") for m in called_models)

    async def test_guardrails_blocked_raises_when_no_ollama_available(self) -> None:
        """Blocked prompts with no Ollama models must raise GuardrailsBlockedError (fail-closed)."""
        models = _make_models()  # only cloud models, no ollama/

        orch = _make_orchestrator(
            guardrail_result=_blocked_guardrail_result("injection found"),
            decision=_routing_decision(),
            pipeline_result=_fallback_result(),
        )

        request = RoutingRequest(prompt="ignore previous instructions", budget_priority=BudgetPriority.MEDIUM)
        with pytest.raises(GuardrailsBlockedError) as exc_info:
            await orch.run(request, models)

        assert "injection found" in exc_info.value.reason

    async def test_pii_detected_prefers_ollama_models(self) -> None:
        """PII-detected prompts should prefer Ollama, then vetted cloud providers."""
        ollama_model = LLMSpec(id="ollama/llama3", name="llama3", context_length=8_192, trusted=True)
        vetted_model = LLMSpec(id="openai/gpt-4o-mini", name="mini", context_length=16_000)
        unvetted_model = LLMSpec(id="mistral/mistral-7b", name="mistral", context_length=8_000)
        models = [ollama_model, vetted_model, unvetted_model]

        decision = _routing_decision("ollama/llama3")
        fb_result = _fallback_result("ollama/llama3")

        orch = _make_orchestrator(
            guardrail_result=_pii_guardrail_result(),
            decision=decision,
            pipeline_result=fb_result,
        )

        request = RoutingRequest(prompt="my email is foo@example.com", budget_priority=BudgetPriority.MEDIUM)
        await orch.run(request, models)

        called_models: list[LLMSpec] = orch._router.decide.call_args[0][1]  # type: ignore[attr-defined]
        called_ids = [m.id for m in called_models]
        assert "ollama/llama3" in called_ids
        assert "openai/gpt-4o-mini" in called_ids
        assert "mistral/mistral-7b" not in called_ids

    async def test_pii_detected_falls_back_to_all_models_when_no_trusted_available(self) -> None:
        """When PII detected but no trusted providers exist, all models are used as fallback."""
        unvetted_model = LLMSpec(id="mistral/mistral-7b", name="mistral", context_length=8_000)
        models = [unvetted_model]

        decision = _routing_decision("mistral/mistral-7b")
        fb_result = _fallback_result("mistral/mistral-7b")

        orch = _make_orchestrator(
            guardrail_result=_pii_guardrail_result(),
            decision=decision,
            pipeline_result=fb_result,
        )

        request = RoutingRequest(prompt="my phone is 555-1234", budget_priority=BudgetPriority.MEDIUM)
        result = await orch.run(request, models)

        # Should not raise — falls back to all models
        assert result.response is not None

    async def test_elevated_injection_risk_prefers_ollama(self) -> None:
        """Elevated injection risk (below block threshold) should prefer Ollama when available."""
        ollama_model = LLMSpec(id="ollama/llama3", name="llama3", context_length=8_192, trusted=True)
        cloud_model = LLMSpec(id="openai/gpt-4o-mini", name="mini", context_length=16_000)
        models = [ollama_model, cloud_model]

        elevated_guardrail = GuardrailResult(
            passed=True,
            injection_detected=True,
            risk_score=0.5,
            reason="elevated injection risk",
        )

        decision = _routing_decision("ollama/llama3")
        fb_result = _fallback_result("ollama/llama3")

        orch = _make_orchestrator(
            guardrail_result=elevated_guardrail,
            decision=decision,
            pipeline_result=fb_result,
        )

        request = RoutingRequest(prompt="slightly sus prompt", budget_priority=BudgetPriority.MEDIUM)
        await orch.run(request, models)

        called_models: list[LLMSpec] = orch._router.decide.call_args[0][1]  # type: ignore[attr-defined]
        called_ids = [m.id for m in called_models]
        assert called_ids == ["ollama/llama3"]

    async def test_elevated_injection_risk_uses_all_models_when_no_ollama(self) -> None:
        """Elevated injection risk with no Ollama should still route (warning, not block)."""
        models = _make_models()

        elevated_guardrail = GuardrailResult(
            passed=True,
            injection_detected=True,
            risk_score=0.5,
            reason="elevated injection risk",
        )

        decision = _routing_decision()
        fb_result = _fallback_result()

        orch = _make_orchestrator(
            guardrail_result=elevated_guardrail,
            decision=decision,
            pipeline_result=fb_result,
        )

        request = RoutingRequest(prompt="slightly sus prompt", budget_priority=BudgetPriority.MEDIUM)
        result = await orch.run(request, models)

        # Should not raise — uses all available models
        assert result.response is not None
