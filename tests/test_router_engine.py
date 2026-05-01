"""Tests for ear.router_engine — intent classification, scoring, and ranking.

Stubs: full implementation tests added in M2 (E3).
"""
from __future__ import annotations

import pytest

from ear.models import BudgetPriority, RoutingRequest, TaskType
from ear.router_engine import IntentClassifier, RouterEngine, SuitabilityScorer


class TestIntentClassifierInit:
    def test_instantiation(self) -> None:
        classifier = IntentClassifier()
        assert classifier is not None

    def test_classify_not_implemented(self) -> None:
        classifier = IntentClassifier()
        with pytest.raises(NotImplementedError):
            classifier.classify("Hello world")


class TestSuitabilityScorerInit:
    def test_instantiation(self) -> None:
        scorer = SuitabilityScorer()
        assert scorer is not None

    def test_score_not_implemented(self, sample_llm_spec) -> None:  # type: ignore[no-untyped-def]
        scorer = SuitabilityScorer()
        with pytest.raises(NotImplementedError):
            scorer.score(sample_llm_spec, TaskType.SIMPLE, BudgetPriority.MEDIUM)


class TestRouterEngineInit:
    def test_instantiation(self) -> None:
        engine = RouterEngine()
        assert engine is not None

    def test_decide_not_implemented(self, sample_llm_spec) -> None:  # type: ignore[no-untyped-def]
        engine = RouterEngine()
        request = RoutingRequest(prompt="Test prompt")
        with pytest.raises(NotImplementedError):
            engine.decide(request, [sample_llm_spec])

    def test_filter_eligible_not_implemented(self, sample_llm_spec) -> None:  # type: ignore[no-untyped-def]
        engine = RouterEngine()
        with pytest.raises(NotImplementedError):
            engine._filter_eligible("Hello", [sample_llm_spec])

    def test_rank_candidates_not_implemented(self, sample_llm_spec) -> None:  # type: ignore[no-untyped-def]
        engine = RouterEngine()
        with pytest.raises(NotImplementedError):
            engine._rank_candidates([sample_llm_spec], TaskType.CODING, BudgetPriority.HIGH)
