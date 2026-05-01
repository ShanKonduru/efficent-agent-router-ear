"""Fallback pipeline — retries transient failures and cascades to next candidate."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ear.models import RoutingDecision

logger = logging.getLogger(__name__)

# HTTP status codes considered transient (worth retrying or cascading).
TRANSIENT_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


class ProviderError(Exception):
    """Raised when a model provider returns an error response."""

    def __init__(self, model_id: str, status_code: int, message: str) -> None:
        self.model_id = model_id
        self.status_code = status_code
        self.message = message
        super().__init__(f"{model_id} returned {status_code}: {message}")


class AllCandidatesExhausted(Exception):
    """Raised when every candidate in the fallback chain has failed."""

    def __init__(self, attempts: list[str]) -> None:
        self.attempts = attempts
        super().__init__(
            f"All candidates exhausted after trying: {', '.join(attempts)}"
        )


@dataclass
class FallbackAttempt:
    """Record of a single execution attempt within the fallback pipeline."""

    model_id: str
    success: bool
    error: str | None = None


@dataclass
class FallbackResult:
    """Final result from the fallback pipeline after all attempts."""

    model_used: str
    response: Any
    attempts: list[FallbackAttempt] = field(default_factory=list)
    succeeded: bool = True


class FailureClassifier:
    """Determines whether a provider error is transient or fatal."""

    def is_transient(self, error: ProviderError) -> bool:
        """Return True if the error warrants a retry or cascade."""
        raise NotImplementedError


class FallbackPipeline:
    """Executes a routing decision with ordered fallback across candidates."""

    def __init__(
        self,
        max_retries: int = 3,
        classifier: FailureClassifier | None = None,
    ) -> None:
        self._max_retries = max_retries
        self._classifier = classifier or FailureClassifier()

    async def execute(
        self,
        decision: RoutingDecision,
        prompt: str,
    ) -> FallbackResult:
        """Execute the prompt against the selected model with cascade fallback.

        Raises AllCandidatesExhausted if every candidate fails.
        """
        raise NotImplementedError

    async def _call_model(self, model_id: str, prompt: str) -> Any:
        """Send the prompt to a specific model and return the raw response."""
        raise NotImplementedError
