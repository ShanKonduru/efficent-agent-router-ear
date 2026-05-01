"""Tests for ear.fallback — failure classification and cascade pipeline.

Stubs: full implementation tests added in M2 (E5).
"""
from __future__ import annotations

import pytest

from ear.fallback import (
    AllCandidatesExhausted,
    FailureClassifier,
    FallbackPipeline,
    ProviderError,
)
from ear.models import RoutingDecision, TaskType


class TestProviderError:
    def test_attributes(self) -> None:
        err = ProviderError("openai/gpt-4o", 429, "rate limited")
        assert err.model_id == "openai/gpt-4o"
        assert err.status_code == 429
        assert "429" in str(err)


class TestAllCandidatesExhausted:
    def test_attributes(self) -> None:
        err = AllCandidatesExhausted(["openai/gpt-4o", "anthropic/claude-3.5-sonnet"])
        assert len(err.attempts) == 2


class TestFailureClassifierInit:
    def test_instantiation(self) -> None:
        classifier = FailureClassifier()
        assert classifier is not None

    def test_is_transient_not_implemented(self) -> None:
        classifier = FailureClassifier()
        with pytest.raises(NotImplementedError):
            classifier.is_transient(ProviderError("m", 429, "rate limited"))


class TestFallbackPipelineInit:
    def test_instantiation(self) -> None:
        pipeline = FallbackPipeline(max_retries=3)
        assert pipeline is not None

    async def test_execute_not_implemented(self) -> None:
        pipeline = FallbackPipeline()
        decision = RoutingDecision(
            selected_model="openai/gpt-4o",
            task_type=TaskType.SIMPLE,
            suitability_score=0.5,
            reason="stub",
        )
        with pytest.raises(NotImplementedError):
            await pipeline.execute(decision, "test prompt")
