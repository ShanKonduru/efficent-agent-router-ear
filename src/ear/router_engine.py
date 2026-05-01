"""Router engine — classifies intent, scores candidates, and builds fallback chains."""
from __future__ import annotations

import logging

from ear.models import (
    BudgetPriority,
    LLMSpec,
    RoutingDecision,
    RoutingRequest,
    TaskType,
)

logger = logging.getLogger(__name__)

# Context length threshold above which only mega-context models are eligible.
MEGA_CONTEXT_THRESHOLD = 100_000

# Budget priority weight multipliers applied to the cost factor in scoring.
BUDGET_COST_WEIGHTS: dict[BudgetPriority, float] = {
    BudgetPriority.LOW: 3.0,
    BudgetPriority.MEDIUM: 1.5,
    BudgetPriority.HIGH: 0.5,
}

# Model IDs that are eligible when context exceeds MEGA_CONTEXT_THRESHOLD.
MEGA_CONTEXT_MODELS: frozenset[str] = frozenset(
    {
        "google/gemini-1.5-pro",
        "anthropic/claude-3-opus",
        "anthropic/claude-3.5-sonnet",
    }
)

# Models preferred for coding tasks.
CODING_PREFERRED_MODELS: frozenset[str] = frozenset(
    {
        "openai/gpt-4o",
        "anthropic/claude-3.5-sonnet",
        "openai/gpt-4o-mini",
    }
)


class IntentClassifier:
    """Classifies a prompt into a TaskType using deterministic heuristics."""

    def classify(self, prompt: str) -> TaskType:
        """Return the TaskType for the given prompt."""
        raise NotImplementedError


class SuitabilityScorer:
    """Computes a suitability score S = Quality / (Cost * Latency) for each candidate."""

    def score(
        self,
        spec: LLMSpec,
        task_type: TaskType,
        budget_priority: BudgetPriority,
    ) -> float:
        """Return a non-negative suitability score; higher is better."""
        raise NotImplementedError


class RouterEngine:
    """Core decision engine that selects the best model for a routing request."""

    def __init__(
        self,
        classifier: IntentClassifier | None = None,
        scorer: SuitabilityScorer | None = None,
    ) -> None:
        self._classifier = classifier or IntentClassifier()
        self._scorer = scorer or SuitabilityScorer()

    def decide(
        self,
        request: RoutingRequest,
        available_models: list[LLMSpec],
    ) -> RoutingDecision:
        """Evaluate candidates and return a RoutingDecision with a fallback chain.

        Raises ValueError if no eligible candidates exist.
        """
        raise NotImplementedError

    def _filter_eligible(
        self,
        prompt: str,
        models: list[LLMSpec],
    ) -> list[LLMSpec]:
        """Apply context-window and mega-context eligibility filters."""
        raise NotImplementedError

    def _rank_candidates(
        self,
        models: list[LLMSpec],
        task_type: TaskType,
        budget_priority: BudgetPriority,
    ) -> list[tuple[LLMSpec, float]]:
        """Return models sorted by descending suitability score."""
        raise NotImplementedError
