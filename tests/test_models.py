"""Tests for ear.models — domain model validation."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from ear.models import (
    BudgetPriority,
    ControllerHint,
    GuardrailResult,
    LLMPricing,
    LLMSpec,
    RouteMetric,
    RoutingDecision,
    RoutingRequest,
    SessionSummary,
    TaskType,
)


class TestLLMSpec:
    def test_valid_spec(self) -> None:
        spec = LLMSpec(id="openai/gpt-4o", context_length=128_000)
        assert spec.id == "openai/gpt-4o"
        assert spec.pricing is None

    def test_blank_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            LLMSpec(id="  ", context_length=128_000)

    def test_zero_context_raises(self) -> None:
        with pytest.raises(ValidationError):
            LLMSpec(id="openai/gpt-4o", context_length=0)

    def test_with_pricing(self) -> None:
        spec = LLMSpec(
            id="openai/gpt-4o",
            context_length=128_000,
            pricing=LLMPricing(prompt=0.000005, completion=0.000015),
        )
        assert spec.pricing is not None
        assert spec.pricing.prompt == 0.000005


class TestRoutingRequest:
    def test_valid_request(self) -> None:
        req = RoutingRequest(prompt="Explain asyncio.")
        assert req.budget_priority == BudgetPriority.MEDIUM
        assert req.task_type is None

    def test_blank_prompt_raises(self) -> None:
        with pytest.raises(ValidationError):
            RoutingRequest(prompt="   ")

    def test_explicit_task_and_budget(self) -> None:
        req = RoutingRequest(
            prompt="Write a sorting algorithm.",
            task_type=TaskType.CODING,
            budget_priority=BudgetPriority.LOW,
        )
        assert req.task_type == TaskType.CODING
        assert req.budget_priority == BudgetPriority.LOW

    def test_request_accepts_controller_hint(self) -> None:
        req = RoutingRequest(
            prompt="Plan this migration.",
            controller_hint=ControllerHint(task_type=TaskType.PLANNING, confidence=0.9),
        )
        assert req.controller_hint is not None
        assert req.controller_hint.task_type == TaskType.PLANNING


class TestRoutingDecision:
    def test_valid_decision(self) -> None:
        decision = RoutingDecision(
            selected_model="openai/gpt-4o",
            task_type=TaskType.CODING,
            suitability_score=0.85,
            reason="Code block detected; coding specialist preferred.",
        )
        assert decision.fallback_chain == []

    def test_fallback_chain_preserved(self) -> None:
        decision = RoutingDecision(
            selected_model="openai/gpt-4o",
            fallback_chain=["anthropic/claude-3.5-sonnet"],
            task_type=TaskType.CODING,
            suitability_score=0.85,
            reason="Primary with fallback.",
        )
        assert "anthropic/claude-3.5-sonnet" in decision.fallback_chain


class TestGuardrailResult:
    def test_passing_result(self) -> None:
        result = GuardrailResult(passed=True)
        assert not result.injection_detected
        assert not result.pii_detected

    def test_failing_result(self) -> None:
        result = GuardrailResult(passed=False, injection_detected=True, reason="Jailbreak pattern detected.")
        assert result.reason is not None


class TestControllerHint:
    def test_valid_hint(self) -> None:
        hint = ControllerHint(
            task_type=TaskType.CODING,
            preferred_model="openai/gpt-4o-mini",
            allowed_models=["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet"],
            confidence=0.92,
        )
        assert hint.confidence == 0.92

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            ControllerHint.model_validate(
                {
                    "task_type": "coding",
                    "confidence": 0.9,
                    "unexpected": "not-allowed",
                }
            )

    def test_blank_preferred_model_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ControllerHint(preferred_model="  ", confidence=0.8)

    def test_blank_allowed_model_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ControllerHint(allowed_models=["openai/gpt-4o", " "], confidence=0.8)


class TestSessionSummary:
    def test_defaults(self) -> None:
        summary = SessionSummary()
        assert summary.total_calls == 0
        assert summary.total_cost_usd == 0.0
        assert summary.calls_by_model == {}
