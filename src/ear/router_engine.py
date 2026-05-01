"""Router engine — classifies intent, scores candidates, and builds fallback chains."""
from __future__ import annotations

import logging
import math

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

# Keyword sets used by IntentClassifier (lowercase, checked against lowercased prompt).
_CODING_KEYWORDS: frozenset[str] = frozenset(
    {
        "def ", "class ", "import ", "function ", "algorithm", "debug",
        "refactor", "implement", "code", "script", "program", "=>",
    }
)

_PLANNING_KEYWORDS: frozenset[str] = frozenset(
    {
        "plan", "roadmap", "strategy", "step by step", "steps to", "outline",
        "design", "architecture", "sequence", "schedule", "milestone",
    }
)

_RESEARCH_KEYWORDS: frozenset[str] = frozenset(
    {
        "research", "survey", "summarize", "compare", "difference between",
        "explain", "what is", "literature", "study", "analyze", "review",
    }
)

# Default per-token cost used when a model carries no pricing data.
_DEFAULT_COST_PER_TOKEN: float = 0.001
# Quality bonus for task-affinity match (e.g. coding model on coding task).
_AFFINITY_BONUS: float = 0.3
# Small constant preventing division-by-zero in the scoring formula.
_EPSILON: float = 1e-9


class IntentClassifier:
    """Classifies a prompt into a TaskType using deterministic heuristics."""

    def classify(self, prompt: str) -> TaskType:
        """Return the TaskType for the given *prompt*.

        Detection order (highest specificity first):

        1. Any fenced code block (triple-backtick) → ``CODING``
        2. Keyword vote among CODING / PLANNING / RESEARCH sets; winner wins.
        3. Tie or no signals → ``SIMPLE``.
        """
        # Fenced code block is an unambiguous coding signal.
        if "```" in prompt:
            return TaskType.CODING

        lower = prompt.lower()
        coding_hits = sum(1 for kw in _CODING_KEYWORDS if kw in lower)
        planning_hits = sum(1 for kw in _PLANNING_KEYWORDS if kw in lower)
        research_hits = sum(1 for kw in _RESEARCH_KEYWORDS if kw in lower)

        max_hits = max(coding_hits, planning_hits, research_hits)

        if max_hits == 0:
            return TaskType.SIMPLE
        if coding_hits == max_hits:
            return TaskType.CODING
        if planning_hits == max_hits:
            return TaskType.PLANNING
        return TaskType.RESEARCH


class SuitabilityScorer:
    """Computes a suitability score S = Quality / (Cost × Latency) for each candidate.

    *Quality* is a log-normalized context-length proxy plus a task-affinity
    bonus for preferred model / task-type pairings.

    *Cost* is the sum of prompt and completion pricing weighted by the budget
    priority multiplier from ``BUDGET_COST_WEIGHTS``.

    *Latency* is not modelled separately because no real per-model latency
    measurements are available at routing time.  Instead, latency tie-breaking
    is handled purely in :meth:`RouterEngine._rank_candidates` by ordering
    equal-score models by ascending context length (smaller context ≈ faster
    response).  Mixing an estimated latency proxy into the formula would create
    a circular dependency with the quality proxy (both derived from
    ``context_length``) and produce unstable rankings.
    """

    def score(
        self,
        spec: LLMSpec,
        task_type: TaskType,
        budget_priority: BudgetPriority,
    ) -> float:
        """Return a non-negative suitability score; higher is better.

        Formula: ``S = quality / (cost_weighted + ε)``

        * ``quality`` — log-normalized context length in [0, 1] plus an
          optional affinity bonus for task-type / model pairings.
        * ``cost_weighted`` — per-token cost scaled by the budget priority
          multiplier so that ``LOW`` budget amplifies cost sensitivity and
          ``HIGH`` budget reduces it.
        """
        # Quality: log-normalized context length (0–1 range) plus affinity bonus.
        quality = math.log1p(spec.context_length) / math.log1p(2_000_000)
        if task_type == TaskType.CODING and spec.id in CODING_PREFERRED_MODELS:
            quality += _AFFINITY_BONUS

        # Cost: raw per-token cost amplified by budget weight.
        if spec.pricing is not None:
            raw_cost = spec.pricing.prompt + spec.pricing.completion
        else:
            raw_cost = _DEFAULT_COST_PER_TOKEN
        cost_weighted = raw_cost * BUDGET_COST_WEIGHTS[budget_priority]

        return quality / (cost_weighted + _EPSILON)


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

        Args:
            request: Routing request containing prompt and optional hints.
            available_models: All models available for selection.

        Returns:
            A ``RoutingDecision`` with the chosen model and an ordered fallback chain.

        Raises:
            ValueError: If no eligible candidates exist after filtering.
        """
        task_type = request.task_type or self._classifier.classify(request.prompt)

        eligible = self._filter_eligible(request.prompt, available_models)
        if not eligible:
            raise ValueError(
                f"No eligible models for prompt of length {len(request.prompt)} chars. "
                f"Available: {[m.id for m in available_models]}"
            )

        ranked = self._rank_candidates(eligible, task_type, request.budget_priority)
        selected, score = ranked[0]
        fallback_chain = [m.id for m, _ in ranked[1:]]

        reason = (
            f"Selected {selected.id!r} for {task_type.value} task "
            f"(score={score:.4f}, budget={request.budget_priority.value})"
        )
        logger.info(
            "Routing decision: model=%s score=%.4f task=%s budget=%s fallback_count=%d",
            selected.id,
            score,
            task_type.value,
            request.budget_priority.value,
            len(fallback_chain),
        )

        return RoutingDecision(
            selected_model=selected.id,
            fallback_chain=fallback_chain,
            task_type=task_type,
            suitability_score=score,
            reason=reason,
        )

    def _filter_eligible(
        self,
        prompt: str,
        models: list[LLMSpec],
    ) -> list[LLMSpec]:
        """Apply context-window and mega-context eligibility filters.

        When *prompt* exceeds ``MEGA_CONTEXT_THRESHOLD`` characters, only models
        in ``MEGA_CONTEXT_MODELS`` are returned so short-context models are never
        selected for very large inputs.
        """
        if len(prompt) > MEGA_CONTEXT_THRESHOLD:
            return [m for m in models if m.id in MEGA_CONTEXT_MODELS]
        return list(models)

    def _rank_candidates(
        self,
        models: list[LLMSpec],
        task_type: TaskType,
        budget_priority: BudgetPriority,
    ) -> list[tuple[LLMSpec, float]]:
        """Return *(model, score)* pairs sorted by descending suitability score.

        Tie-breaking: when two models share the same score, the one with the
        smaller context length (proxy for lower latency) is ranked first.
        """
        scored = [
            (m, self._scorer.score(m, task_type, budget_priority)) for m in models
        ]
        return sorted(scored, key=lambda x: (-x[1], x[0].context_length))
