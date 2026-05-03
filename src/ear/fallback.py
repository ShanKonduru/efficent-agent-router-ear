"""Fallback pipeline — retries transient failures and cascades to next candidate."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import httpx

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

    def is_transient(self, error: Exception) -> bool:
        """Return True if the error warrants a retry or cascade.

        Network-level errors (ConnectError, ReadError, WriteError, etc.) are
        treated as transient so the fallback pipeline cascades to the next
        candidate instead of surfacing a raw ``httpx`` exception to the caller.
        """
        if isinstance(error, ProviderError):
            return error.status_code in TRANSIENT_STATUS_CODES
        if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
            return True
        # httpx network errors (ConnectError, ReadError, WriteError, …) and
        # httpx-level timeouts (ConnectTimeout, ReadTimeout, etc.) are transient.
        return isinstance(error, (httpx.NetworkError, httpx.TimeoutException))


class FallbackPipeline:
    """Executes a routing decision with ordered fallback across candidates."""

    def __init__(
        self,
        max_retries: int = 3,
        classifier: FailureClassifier | None = None,
        base_backoff_seconds: float = 0.1,
        max_backoff_seconds: float = 2.0,
        sleep_func: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if base_backoff_seconds < 0:
            raise ValueError("base_backoff_seconds must be >= 0")
        if max_backoff_seconds < 0:
            raise ValueError("max_backoff_seconds must be >= 0")
        if base_backoff_seconds > max_backoff_seconds:
            raise ValueError("base_backoff_seconds must be <= max_backoff_seconds")

        self._max_retries = max_retries
        self._classifier = classifier or FailureClassifier()
        self._base_backoff_seconds = base_backoff_seconds
        self._max_backoff_seconds = max_backoff_seconds
        self._sleep = sleep_func or asyncio.sleep

    async def execute(
        self,
        decision: RoutingDecision,
        prompt: str,
    ) -> FallbackResult:
        """Execute the prompt against the selected model with cascade fallback.

        Raises AllCandidatesExhausted if every candidate fails.
        """
        attempts: list[FallbackAttempt] = []
        candidates = self._build_candidate_chain(decision)

        for model_id in candidates:
            retry_index = 0
            while True:
                try:
                    response = await self._call_model(model_id, prompt)
                    attempts.append(FallbackAttempt(model_id=model_id, success=True))
                    return FallbackResult(
                        model_used=model_id,
                        response=response,
                        attempts=attempts,
                        succeeded=True,
                    )
                except Exception as error:  # noqa: BLE001
                    attempts.append(
                        FallbackAttempt(
                            model_id=model_id,
                            success=False,
                            error=str(error),
                        )
                    )

                    transient = self._classifier.is_transient(error)
                    should_retry = transient and retry_index < self._max_retries
                    if not should_retry:
                        logger.warning(
                            "Model '%s' failed (%s). Cascading to next candidate.",
                            model_id,
                            type(error).__name__,
                        )
                        break

                    retry_index += 1
                    backoff_seconds = min(
                        self._base_backoff_seconds * (2 ** (retry_index - 1)),
                        self._max_backoff_seconds,
                    )
                    logger.info(
                        "Transient failure from '%s'; retry %s/%s in %.3fs.",
                        model_id,
                        retry_index,
                        self._max_retries,
                        backoff_seconds,
                    )
                    await self._sleep(backoff_seconds)

        raise AllCandidatesExhausted([attempt.model_id for attempt in attempts])

    @staticmethod
    def _build_candidate_chain(decision: RoutingDecision) -> list[str]:
        """Return selected model followed by de-duplicated fallback chain."""
        chain: list[str] = []
        seen: set[str] = set()
        for model_id in [decision.selected_model, *decision.fallback_chain]:
            if model_id not in seen:
                seen.add(model_id)
                chain.append(model_id)
        return chain

    async def _call_model(self, model_id: str, prompt: str) -> Any:
        """Send the prompt to a specific model and return the raw response."""
        raise NotImplementedError
