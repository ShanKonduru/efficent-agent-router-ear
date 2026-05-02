"""Router engine — classifies intent, scores candidates, and builds fallback chains."""
from __future__ import annotations

import logging
import math

from ear.intent import HeuristicIntentClassifier, IntentClassifier
from ear.models import (
    BudgetPriority,
    ControllerHint,
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

# Default per-token cost used when a model carries no pricing data.
_DEFAULT_COST_PER_TOKEN: float = 0.001
# Quality bonus for task-affinity match (e.g. coding model on coding task).
_AFFINITY_BONUS: float = 0.3
# Small constant preventing division-by-zero in the scoring formula.
_EPSILON: float = 1e-9

# Mini-controller merge policy (deterministic thresholds/weights).
_HINT_TASK_TYPE_CONFIDENCE_THRESHOLD: float = 0.80
_HINT_ALLOWED_MODELS_CONFIDENCE_THRESHOLD: float = 0.70
_HINT_PREFERRED_MODEL_CONFIDENCE_THRESHOLD: float = 0.85
_HINT_PREFERRED_MODEL_SCORE_BONUS: float = 0.20


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
        self._classifier = classifier or HeuristicIntentClassifier()
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
        task_type = self._resolve_task_type(request)

        eligible = self._filter_eligible(request.prompt, available_models)
        eligible = self._apply_allowed_model_hint(eligible, request.controller_hint)
        if not eligible:
            raise ValueError(
                f"No eligible models for prompt of length {len(request.prompt)} chars. "
                f"Available: {[m.id for m in available_models]}"
            )

        ranked = self._rank_candidates(
            eligible,
            task_type,
            request.budget_priority,
            request.controller_hint,
        )
        selected, score = ranked[0]
        fallback_chain = [m.id for m, _ in ranked[1:]]

        reason = (
            f"Selected {selected.id!r} for {task_type.value} task "
            f"(score={score:.4f}, budget={request.budget_priority.value})"
        )
        if self._is_preferred_model_hint_applied(selected.id, request.controller_hint):
            reason += " [controller_hint:preferred_model_applied]"
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
        controller_hint: ControllerHint | None = None,
    ) -> list[tuple[LLMSpec, float]]:
        """Return *(model, score)* pairs sorted by descending suitability score.

        Tie-breaking: when two models share the same score, the one with the
        smaller context length (proxy for lower latency) is ranked first.
        """
        scored: list[tuple[LLMSpec, float]] = []
        for model in models:
            score = self._scorer.score(model, task_type, budget_priority)
            if self._is_preferred_model_hint_applied(model.id, controller_hint):
                score += _HINT_PREFERRED_MODEL_SCORE_BONUS
            scored.append((model, score))

        return sorted(scored, key=lambda x: (-x[1], x[0].context_length))

    def _resolve_task_type(self, request: RoutingRequest) -> TaskType:
        """Resolve task type from explicit request, hint, or classifier (in that order)."""
        if request.task_type is not None:
            return request.task_type

        hint = request.controller_hint
        if (
            hint is not None
            and hint.task_type is not None
            and hint.confidence >= _HINT_TASK_TYPE_CONFIDENCE_THRESHOLD
        ):
            return hint.task_type

        return self._classifier.classify(request.prompt)

    def _apply_allowed_model_hint(
        self,
        models: list[LLMSpec],
        controller_hint: ControllerHint | None,
    ) -> list[LLMSpec]:
        """Apply allow-list hint only when confidence is high and intersection is non-empty."""
        if (
            controller_hint is None
            or not controller_hint.allowed_models
            or controller_hint.confidence < _HINT_ALLOWED_MODELS_CONFIDENCE_THRESHOLD
        ):
            return models

        allowed_ids = set(controller_hint.allowed_models)
        restricted = [m for m in models if m.id in allowed_ids]

        # Deterministic safety: ignore the hint if it eliminates all candidates.
        return restricted if restricted else models

    def _is_preferred_model_hint_applied(
        self,
        model_id: str,
        controller_hint: ControllerHint | None,
    ) -> bool:
        """Return True when preferred-model hint should influence ranking."""
        return (
            controller_hint is not None
            and controller_hint.preferred_model == model_id
            and controller_hint.confidence >= _HINT_PREFERRED_MODEL_CONFIDENCE_THRESHOLD
        )
