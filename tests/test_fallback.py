"""Tests for ear.fallback — failure classification and cascade pipeline."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
import httpx

from ear.fallback import (
    AllCandidatesExhausted,
    FallbackAttempt,
    FallbackResult,
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
        assert err.message == "rate limited"
        assert "429" in str(err)


class TestAllCandidatesExhausted:
    def test_attributes(self) -> None:
        err = AllCandidatesExhausted(["openai/gpt-4o", "anthropic/claude-3.5-sonnet"])
        assert len(err.attempts) == 2
        assert "openai/gpt-4o" in str(err)


class TestFailureClassifier:
    def test_instantiation(self) -> None:
        classifier = FailureClassifier()
        assert classifier is not None

    def test_is_transient_true_for_transient_provider_status(self) -> None:
        classifier = FailureClassifier()
        assert classifier.is_transient(ProviderError("m", 429, "rate limited"))

    def test_is_transient_false_for_non_transient_provider_status(self) -> None:
        classifier = FailureClassifier()
        assert not classifier.is_transient(ProviderError("m", 400, "bad request"))

    def test_is_transient_true_for_timeout_errors(self) -> None:
        classifier = FailureClassifier()
        assert classifier.is_transient(asyncio.TimeoutError())
        assert classifier.is_transient(TimeoutError())

    def test_is_transient_false_for_other_exception_types(self) -> None:
        classifier = FailureClassifier()
        assert not classifier.is_transient(ValueError("malformed json"))

    def test_is_transient_true_for_httpx_network_error(self) -> None:
        classifier = FailureClassifier()
        assert classifier.is_transient(httpx.ConnectError("All connection attempts failed"))
        assert classifier.is_transient(httpx.ReadError("connection reset"))
        assert classifier.is_transient(httpx.WriteError("broken pipe"))

    def test_is_transient_true_for_httpx_timeout_exception(self) -> None:
        classifier = FailureClassifier()
        assert classifier.is_transient(httpx.ConnectTimeout("timed out"))
        assert classifier.is_transient(httpx.ReadTimeout("timed out"))
        assert classifier.is_transient(httpx.PoolTimeout("timed out"))


class _ScriptedPipeline(FallbackPipeline):
    def __init__(
        self,
        scripts: dict[str, list[Any]],
        max_retries: int = 3,
        classifier: FailureClassifier | None = None,
        sleep_func: Callable[[float], Awaitable[None]] | None = None,
        base_backoff_seconds: float = 0.1,
        max_backoff_seconds: float = 2.0,
    ) -> None:
        super().__init__(
            max_retries=max_retries,
            classifier=classifier,
            sleep_func=sleep_func,
            base_backoff_seconds=base_backoff_seconds,
            max_backoff_seconds=max_backoff_seconds,
        )
        self._scripts = {k: list(v) for k, v in scripts.items()}
        self.calls: list[str] = []

    async def _call_model(self, model_id: str, prompt: str) -> Any:
        self.calls.append(model_id)
        queue = self._scripts.get(model_id)
        if not queue:
            raise ProviderError(model_id, 500, "no scripted response")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _decision(primary: str, fallback: list[str] | None = None) -> RoutingDecision:
    return RoutingDecision(
        selected_model=primary,
        fallback_chain=fallback or [],
        task_type=TaskType.SIMPLE,
        suitability_score=0.5,
        reason="test",
    )


class TestFallbackPipelineInit:
    def test_instantiation(self) -> None:
        pipeline = FallbackPipeline(max_retries=3)
        assert pipeline is not None
        assert pipeline._max_retries == 3

    def test_rejects_negative_max_retries(self) -> None:
        with pytest.raises(ValueError, match="max_retries"):
            FallbackPipeline(max_retries=-1)

    def test_rejects_negative_base_backoff(self) -> None:
        with pytest.raises(ValueError, match="base_backoff_seconds"):
            FallbackPipeline(base_backoff_seconds=-0.1)

    def test_rejects_negative_max_backoff(self) -> None:
        with pytest.raises(ValueError, match="max_backoff_seconds"):
            FallbackPipeline(max_backoff_seconds=-1.0)

    def test_rejects_base_backoff_greater_than_max(self) -> None:
        with pytest.raises(ValueError, match="base_backoff_seconds"):
            FallbackPipeline(base_backoff_seconds=2.0, max_backoff_seconds=1.0)

    def test_build_candidate_chain_deduplicates_order(self) -> None:
        decision = _decision(
            "openai/gpt-4o",
            ["openai/gpt-4o", "openai/gpt-4o-mini", "openai/gpt-4o-mini"],
        )
        assert FallbackPipeline._build_candidate_chain(decision) == [
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
        ]

    async def test_execute_returns_on_first_success(self) -> None:
        pipeline = _ScriptedPipeline({"openai/gpt-4o": [{"text": "ok"}]})
        decision = _decision("openai/gpt-4o", ["openai/gpt-4o-mini"])

        result = await pipeline.execute(decision, "prompt")

        assert isinstance(result, FallbackResult)
        assert result.succeeded
        assert result.model_used == "openai/gpt-4o"
        assert result.response == {"text": "ok"}
        assert result.attempts == [FallbackAttempt(model_id="openai/gpt-4o", success=True)]
        assert pipeline.calls == ["openai/gpt-4o"]

    async def test_execute_retries_transient_and_then_succeeds(self) -> None:
        sleep_values: list[float] = []

        async def _fake_sleep(seconds: float) -> None:
            sleep_values.append(seconds)

        pipeline = _ScriptedPipeline(
            {
                "openai/gpt-4o": [
                    ProviderError("openai/gpt-4o", 429, "rate limited"),
                    {"text": "ok-after-retry"},
                ]
            },
            max_retries=2,
            sleep_func=_fake_sleep,
        )
        decision = _decision("openai/gpt-4o")

        result = await pipeline.execute(decision, "prompt")

        assert result.model_used == "openai/gpt-4o"
        assert len(result.attempts) == 2
        assert not result.attempts[0].success
        assert result.attempts[1].success
        assert sleep_values == [0.1]

    async def test_execute_retries_then_cascades_to_next_model(self) -> None:
        sleep_values: list[float] = []

        async def _fake_sleep(seconds: float) -> None:
            sleep_values.append(seconds)

        pipeline = _ScriptedPipeline(
            {
                "openai/gpt-4o": [
                    ProviderError("openai/gpt-4o", 503, "unavailable"),
                    ProviderError("openai/gpt-4o", 503, "still unavailable"),
                ],
                "openai/gpt-4o-mini": [{"text": "fallback-ok"}],
            },
            max_retries=1,
            sleep_func=_fake_sleep,
        )
        decision = _decision("openai/gpt-4o", ["openai/gpt-4o-mini"])

        result = await pipeline.execute(decision, "prompt")

        assert result.model_used == "openai/gpt-4o-mini"
        assert [a.model_id for a in result.attempts] == [
            "openai/gpt-4o",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
        ]
        assert sleep_values == [0.1]

    async def test_execute_does_not_retry_fatal_error_and_cascades(self) -> None:
        sleep_values: list[float] = []

        async def _fake_sleep(seconds: float) -> None:
            sleep_values.append(seconds)

        pipeline = _ScriptedPipeline(
            {
                "openai/gpt-4o": [ProviderError("openai/gpt-4o", 400, "bad request")],
                "openai/gpt-4o-mini": [{"text": "ok"}],
            },
            max_retries=5,
            sleep_func=_fake_sleep,
        )
        decision = _decision("openai/gpt-4o", ["openai/gpt-4o-mini"])

        result = await pipeline.execute(decision, "prompt")

        assert result.model_used == "openai/gpt-4o-mini"
        assert sleep_values == []

    async def test_execute_uses_injected_classifier(self) -> None:
        class _NeverTransient(FailureClassifier):
            def is_transient(self, error: Exception) -> bool:
                return False

        pipeline = _ScriptedPipeline(
            {
                "openai/gpt-4o": [ProviderError("openai/gpt-4o", 429, "rate limited")],
                "openai/gpt-4o-mini": [{"text": "ok"}],
            },
            classifier=_NeverTransient(),
            max_retries=3,
        )
        decision = _decision("openai/gpt-4o", ["openai/gpt-4o-mini"])

        result = await pipeline.execute(decision, "prompt")

        assert result.model_used == "openai/gpt-4o-mini"
        assert pipeline.calls == ["openai/gpt-4o", "openai/gpt-4o-mini"]

    async def test_execute_backoff_is_exponential_and_bounded(self) -> None:
        sleep_values: list[float] = []

        async def _fake_sleep(seconds: float) -> None:
            sleep_values.append(seconds)

        pipeline = _ScriptedPipeline(
            {
                "openai/gpt-4o": [
                    ProviderError("openai/gpt-4o", 503, "e1"),
                    ProviderError("openai/gpt-4o", 503, "e2"),
                    ProviderError("openai/gpt-4o", 503, "e3"),
                    ProviderError("openai/gpt-4o", 503, "e4"),
                ]
            },
            max_retries=3,
            base_backoff_seconds=0.5,
            max_backoff_seconds=1.0,
            sleep_func=_fake_sleep,
        )
        decision = _decision("openai/gpt-4o")

        with pytest.raises(AllCandidatesExhausted):
            await pipeline.execute(decision, "prompt")

        assert sleep_values == [0.5, 1.0, 1.0]

    async def test_execute_raises_all_candidates_exhausted_with_attempts(self) -> None:
        pipeline = _ScriptedPipeline(
            {
                "openai/gpt-4o": [ProviderError("openai/gpt-4o", 503, "down")],
                "openai/gpt-4o-mini": [RuntimeError("broken")],
            },
            max_retries=0,
        )
        decision = _decision("openai/gpt-4o", ["openai/gpt-4o-mini"])

        with pytest.raises(AllCandidatesExhausted) as exc:
            await pipeline.execute(decision, "prompt")

        assert exc.value.attempts == ["openai/gpt-4o", "openai/gpt-4o-mini"]

    async def test_base_call_model_still_requires_override(self) -> None:
        pipeline = FallbackPipeline()
        with pytest.raises(NotImplementedError):
            await pipeline._call_model("openai/gpt-4o", "prompt")
