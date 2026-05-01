"""Tests for ear.router_engine — intent classification, scoring, ranking, and routing.

Coverage targets (E3 acceptance criteria from WBS):
- All four TaskType branches in IntentClassifier.classify()
- SuitabilityScorer: quality, affinity bonus, budget weight, no-pricing fallback
- RouterEngine: eligible filter, ranking, tie-breaking, fallback chain, error path
- decide() skips classify when task_type is explicit in the request
"""
from __future__ import annotations

import pytest

from ear.models import BudgetPriority, LLMPricing, LLMSpec, RoutingRequest, TaskType
from ear.router_engine import (
    MEGA_CONTEXT_THRESHOLD,
    IntentClassifier,
    RouterEngine,
    SuitabilityScorer,
)


# ---------------------------------------------------------------------------
# IntentClassifier
# ---------------------------------------------------------------------------

class TestIntentClassifier:
    def setup_method(self) -> None:
        self.clf = IntentClassifier()

    def test_fenced_code_block_returns_coding(self) -> None:
        assert self.clf.classify("```python\nprint('hi')\n```") == TaskType.CODING

    def test_coding_keyword_returns_coding(self) -> None:
        assert self.clf.classify("Please implement this algorithm in Python") == TaskType.CODING

    def test_planning_keyword_returns_planning(self) -> None:
        assert self.clf.classify("Create a roadmap and milestone schedule") == TaskType.PLANNING

    def test_research_keyword_returns_research(self) -> None:
        assert self.clf.classify("Summarize the latest research on LLMs") == TaskType.RESEARCH

    def test_no_signal_returns_simple(self) -> None:
        assert self.clf.classify("Hello, how are you today?") == TaskType.SIMPLE

    def test_coding_wins_over_planning_when_more_hits(self) -> None:
        # "implement" and "code" beat single "plan"
        prompt = "implement the code to create a plan for the algorithm"
        assert self.clf.classify(prompt) == TaskType.CODING

    def test_research_wins_over_planning_when_more_hits(self) -> None:
        # "research", "summarize", "analyze", "review" > single "plan"
        prompt = "research, analyze, and review then summarize findings to plan"
        result = self.clf.classify(prompt)
        assert result == TaskType.RESEARCH


# ---------------------------------------------------------------------------
# SuitabilityScorer
# ---------------------------------------------------------------------------

class TestSuitabilityScorer:
    def setup_method(self) -> None:
        self.scorer = SuitabilityScorer()

    def test_returns_positive_float(self, sample_llm_spec: LLMSpec) -> None:
        score = self.scorer.score(sample_llm_spec, TaskType.SIMPLE, BudgetPriority.MEDIUM)
        assert isinstance(score, float)
        assert score > 0

    def test_no_pricing_uses_default_cost(self) -> None:
        spec = LLMSpec(id="no-pricing/model", context_length=8_000)
        score = self.scorer.score(spec, TaskType.SIMPLE, BudgetPriority.MEDIUM)
        assert score > 0

    def test_coding_affinity_bonus_applied_for_preferred_model(self, sample_llm_spec: LLMSpec) -> None:
        # sample_llm_spec id = "openai/gpt-4o", which is in CODING_PREFERRED_MODELS
        score_coding = self.scorer.score(sample_llm_spec, TaskType.CODING, BudgetPriority.MEDIUM)
        score_simple = self.scorer.score(sample_llm_spec, TaskType.SIMPLE, BudgetPriority.MEDIUM)
        assert score_coding > score_simple

    def test_no_affinity_bonus_for_non_preferred_model(self, mega_context_spec: LLMSpec) -> None:
        # google/gemini-1.5-pro is not in CODING_PREFERRED_MODELS
        score_coding = self.scorer.score(mega_context_spec, TaskType.CODING, BudgetPriority.MEDIUM)
        score_simple = self.scorer.score(mega_context_spec, TaskType.SIMPLE, BudgetPriority.MEDIUM)
        assert score_coding == score_simple

    def test_low_budget_reduces_score_vs_high_budget(self, sample_llm_spec: LLMSpec) -> None:
        score_low = self.scorer.score(sample_llm_spec, TaskType.SIMPLE, BudgetPriority.LOW)
        score_high = self.scorer.score(sample_llm_spec, TaskType.SIMPLE, BudgetPriority.HIGH)
        # Higher budget weight on cost → lower suitability score
        assert score_low < score_high

    def test_cheaper_model_beats_pricier_model_on_low_budget(
        self, sample_llm_spec: LLMSpec, cheap_llm_spec: LLMSpec
    ) -> None:
        score_cheap = self.scorer.score(cheap_llm_spec, TaskType.SIMPLE, BudgetPriority.LOW)
        score_pricey = self.scorer.score(sample_llm_spec, TaskType.SIMPLE, BudgetPriority.LOW)
        assert score_cheap > score_pricey


# ---------------------------------------------------------------------------
# RouterEngine._filter_eligible
# ---------------------------------------------------------------------------

class TestFilterEligible:
    def setup_method(self) -> None:
        self.engine = RouterEngine()

    def test_short_prompt_returns_all_models(self, model_catalog: list[LLMSpec]) -> None:
        result = self.engine._filter_eligible("short prompt", model_catalog)
        assert result == model_catalog

    def test_long_prompt_returns_only_mega_context_models(
        self, model_catalog: list[LLMSpec]
    ) -> None:
        long_prompt = "x" * (MEGA_CONTEXT_THRESHOLD + 1)
        result = self.engine._filter_eligible(long_prompt, model_catalog)
        # Only google/gemini-1.5-pro is in MEGA_CONTEXT_MODELS within the catalog
        assert all(m.id == "google/gemini-1.5-pro" for m in result)
        assert len(result) == 1

    def test_long_prompt_with_no_mega_models_returns_empty(
        self, sample_llm_spec: LLMSpec
    ) -> None:
        long_prompt = "x" * (MEGA_CONTEXT_THRESHOLD + 1)
        result = self.engine._filter_eligible(long_prompt, [sample_llm_spec])
        assert result == []


# ---------------------------------------------------------------------------
# RouterEngine._rank_candidates
# ---------------------------------------------------------------------------

class TestRankCandidates:
    def setup_method(self) -> None:
        self.engine = RouterEngine()

    def test_higher_score_ranked_first(self) -> None:
        # When two models have identical pricing, the higher-quality (larger-context)
        # model should rank first because quality drives the score.
        same_price = LLMPricing(prompt=0.0002, completion=0.0004)
        high_quality = LLMSpec(id="high/quality", context_length=200_000, pricing=same_price)
        low_quality = LLMSpec(id="low/quality", context_length=4_000, pricing=same_price)
        ranked = self.engine._rank_candidates(
            [low_quality, high_quality], TaskType.SIMPLE, BudgetPriority.HIGH
        )
        assert ranked[0][0].id == high_quality.id

    def test_cheap_model_wins_on_low_budget(
        self, sample_llm_spec: LLMSpec, cheap_llm_spec: LLMSpec
    ) -> None:
        ranked = self.engine._rank_candidates(
            [sample_llm_spec, cheap_llm_spec], TaskType.SIMPLE, BudgetPriority.LOW
        )
        assert ranked[0][0].id == cheap_llm_spec.id

    def test_tiebreak_prefers_smaller_context(self) -> None:
        # Two identical-pricing models; tie broken by ascending context_length
        class _FixedScorer(SuitabilityScorer):
            def score(self, spec: LLMSpec, task_type: TaskType, budget_priority: BudgetPriority) -> float:
                return 1.0  # same score for all

        engine = RouterEngine(scorer=_FixedScorer())
        small = LLMSpec(id="small/model", context_length=4_000,
                        pricing=LLMPricing(prompt=0.001, completion=0.002))
        large = LLMSpec(id="large/model", context_length=128_000,
                        pricing=LLMPricing(prompt=0.001, completion=0.002))
        ranked = engine._rank_candidates([large, small], TaskType.SIMPLE, BudgetPriority.MEDIUM)
        assert ranked[0][0].id == "small/model"

    def test_scores_included_in_output(self, sample_llm_spec: LLMSpec) -> None:
        ranked = self.engine._rank_candidates(
            [sample_llm_spec], TaskType.CODING, BudgetPriority.MEDIUM
        )
        assert len(ranked) == 1
        assert ranked[0][1] > 0


# ---------------------------------------------------------------------------
# RouterEngine.decide
# ---------------------------------------------------------------------------

class TestDecide:
    def setup_method(self) -> None:
        self.engine = RouterEngine()

    def test_basic_routing_returns_decision(self, model_catalog: list[LLMSpec]) -> None:
        request = RoutingRequest(prompt="Hello world")
        decision = self.engine.decide(request, model_catalog)
        assert decision.selected_model in {m.id for m in model_catalog}
        assert decision.task_type is not None
        assert decision.suitability_score > 0
        assert isinstance(decision.reason, str)

    def test_explicit_task_type_skips_classifier(self, model_catalog: list[LLMSpec]) -> None:
        # Providing task_type on the request must bypass IntentClassifier
        class _NeverCallClassifier(IntentClassifier):
            def classify(self, prompt: str) -> TaskType:
                raise AssertionError("classify() must not be called when task_type is explicit")

        engine = RouterEngine(classifier=_NeverCallClassifier())
        request = RoutingRequest(prompt="any text", task_type=TaskType.RESEARCH)
        decision = engine.decide(request, model_catalog)
        assert decision.task_type == TaskType.RESEARCH

    def test_fallback_chain_contains_remaining_models(
        self, model_catalog: list[LLMSpec]
    ) -> None:
        request = RoutingRequest(prompt="Hello world")
        decision = self.engine.decide(request, model_catalog)
        all_ids = {m.id for m in model_catalog}
        assert decision.selected_model in all_ids
        assert set(decision.fallback_chain).issubset(all_ids)
        assert decision.selected_model not in decision.fallback_chain
        assert len(decision.fallback_chain) == len(model_catalog) - 1

    def test_raises_when_no_eligible_models(self) -> None:
        # Long prompt but only small-context model available → no eligible after filter
        long_prompt = "x" * (MEGA_CONTEXT_THRESHOLD + 1)
        small = LLMSpec(id="openai/gpt-4o-mini", context_length=16_000,
                        pricing=LLMPricing(prompt=0.001, completion=0.002))
        with pytest.raises(ValueError, match="No eligible models"):
            self.engine.decide(RoutingRequest(prompt=long_prompt), [small])

    def test_coding_prompt_selects_preferred_coding_model(
        self, model_catalog: list[LLMSpec]
    ) -> None:
        # ```python block guarantees CODING classification → coding-preferred model wins.
        # gpt-4o-mini is in CODING_PREFERRED_MODELS AND is the cheapest model in the
        # catalog, so it scores highest: quality boost + lowest cost_weighted.
        request = RoutingRequest(prompt="```python\nprint('hello')\n```")
        decision = self.engine.decide(request, model_catalog)
        assert decision.task_type == TaskType.CODING
        assert decision.selected_model == "openai/gpt-4o-mini"

    def test_single_model_catalog_has_empty_fallback(
        self, sample_llm_spec: LLMSpec
    ) -> None:
        request = RoutingRequest(prompt="Hello world")
        decision = self.engine.decide(request, [sample_llm_spec])
        assert decision.fallback_chain == []

    def test_low_budget_selects_cheapest_model(
        self, sample_llm_spec: LLMSpec, cheap_llm_spec: LLMSpec
    ) -> None:
        request = RoutingRequest(prompt="Hello world", budget_priority=BudgetPriority.LOW)
        decision = self.engine.decide(request, [sample_llm_spec, cheap_llm_spec])
        assert decision.selected_model == cheap_llm_spec.id

    def test_mega_context_prompt_selects_mega_model(
        self, model_catalog: list[LLMSpec]
    ) -> None:
        long_prompt = "x" * (MEGA_CONTEXT_THRESHOLD + 1)
        decision = self.engine.decide(RoutingRequest(prompt=long_prompt), model_catalog)
        assert decision.selected_model == "google/gemini-1.5-pro"
