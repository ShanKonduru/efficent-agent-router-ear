"""Tests for ear.executor — LLMExecutor and ExecutingFallbackPipeline."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ear.executor import ExecutingFallbackPipeline, LLMExecutor, _compute_cost
from ear.fallback import AllCandidatesExhausted, FallbackPipeline, ProviderError
from ear.models import (
    ExecutionResponse,
    LLMPricing,
    LLMSpec,
    RoutingDecision,
    TaskType,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_config(
    base_url: str = "https://openrouter.ai/api/v1",
    timeout: float = 30.0,
    max_retries: int = 3,
) -> Any:
    """Return a minimal config-like object."""
    cfg = MagicMock()
    cfg.ear_openrouter_base_url = base_url
    cfg.openrouter_api_key = "test-key"
    cfg.ear_request_timeout_seconds = timeout
    cfg.ear_max_retries = max_retries
    return cfg


def _openrouter_success_payload(
    model: str = "openai/gpt-4o-mini",
    content: str = "Hello!",
    prompt_tokens: int = 10,
    completion_tokens: int = 20,
) -> dict[str, Any]:
    return {
        "model": model,
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


# ── TestComputeCost ───────────────────────────────────────────────────────────

class TestComputeCost:
    def test_zero_usage(self) -> None:
        assert _compute_cost(0.001, 0.002, 0, 0) == 0.0

    def test_nonzero_usage(self) -> None:
        cost = _compute_cost(0.001, 0.002, 1000, 500)
        assert abs(cost - 2.0) < 1e-9

    def test_fractional(self) -> None:
        cost = _compute_cost(0.0, 0.001, 100, 50)
        assert abs(cost - 0.05) < 1e-9


# ── TestLLMExecutor ───────────────────────────────────────────────────────────

class TestLLMExecutor:
    @pytest.fixture()
    def executor(self) -> LLMExecutor:
        return LLMExecutor(_make_config())

    async def test_execute_success(self, executor: LLMExecutor) -> None:
        payload = _openrouter_success_payload(
            model="openai/gpt-4o-mini",
            content="pong",
            prompt_tokens=5,
            completion_tokens=3,
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = payload

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await executor.execute("openai/gpt-4o-mini", "ping")

        assert isinstance(result, ExecutionResponse)
        assert result.model == "openai/gpt-4o-mini"
        assert result.content == "pong"
        assert result.prompt_tokens == 5
        assert result.completion_tokens == 3
        assert result.total_tokens == 8

    async def test_execute_uses_trailing_slash_stripped_url(self) -> None:
        config = _make_config(base_url="https://openrouter.ai/api/v1/")
        executor = LLMExecutor(config)
        payload = _openrouter_success_payload()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = payload

        captured_urls: list[str] = []

        async def fake_post(url: str, **kwargs: Any) -> Any:
            captured_urls.append(url)
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = fake_post
            mock_client_cls.return_value = mock_client

            await executor.execute("openai/gpt-4o-mini", "hello")

        assert captured_urls[0] == "https://openrouter.ai/api/v1/chat/completions"

    async def test_execute_raises_provider_error_on_4xx(self, executor: LLMExecutor) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "rate limited"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ProviderError) as exc_info:
                await executor.execute("openai/gpt-4o-mini", "hello")

        err = exc_info.value
        assert err.model_id == "openai/gpt-4o-mini"
        assert err.status_code == 429

    async def test_execute_raises_provider_error_on_5xx(self, executor: LLMExecutor) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "service unavailable"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ProviderError) as exc_info:
                await executor.execute("openai/gpt-4o-mini", "hello")

        assert exc_info.value.status_code == 503

    async def test_execute_propagates_timeout_error(self, executor: LLMExecutor) -> None:
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(side_effect=asyncio.TimeoutError())
            mock_client_cls.return_value = mock_client

            with pytest.raises(asyncio.TimeoutError):
                await executor.execute("openai/gpt-4o-mini", "hello")

    async def test_execute_missing_usage_defaults_to_zero(self, executor: LLMExecutor) -> None:
        payload = {
            "model": "openai/gpt-4o-mini",
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            # no "usage" key
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = payload

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await executor.execute("openai/gpt-4o-mini", "hello")

        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert result.total_tokens == 0

    async def test_execute_no_model_field_falls_back_to_requested(self, executor: LLMExecutor) -> None:
        payload = {
            # no "model" key
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = payload

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await executor.execute("openai/gpt-4o-mini", "hello")

        assert result.model == "openai/gpt-4o-mini"

    async def test_execute_empty_choices_returns_empty_content(self, executor: LLMExecutor) -> None:
        payload = {
            "model": "openai/gpt-4o-mini",
            "choices": [],
            "usage": {"prompt_tokens": 2, "completion_tokens": 0, "total_tokens": 2},
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = payload

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await executor.execute("openai/gpt-4o-mini", "hello")

        assert result.content == ""


# ── TestExecutingFallbackPipeline ─────────────────────────────────────────────

class _MockExecutor:
    """Scripted LLMExecutor replacement for pipeline tests."""

    def __init__(self, scripts: dict[str, list[Any]]) -> None:
        self._scripts = {k: list(v) for k, v in scripts.items()}

    async def execute(self, model_id: str, prompt: str) -> ExecutionResponse:
        queue = self._scripts.get(model_id)
        if not queue:
            raise ProviderError(model_id, 500, "no scripted response")
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, ExecutionResponse):
            return item
        raise TypeError(f"Unexpected scripted item type: {type(item)}")


def _response(model: str = "openai/gpt-4o-mini", content: str = "ok") -> ExecutionResponse:
    return ExecutionResponse(model=model, content=content, prompt_tokens=5, completion_tokens=3, total_tokens=8)


def _decision(primary: str, fallback: list[str] | None = None) -> RoutingDecision:
    return RoutingDecision(
        selected_model=primary,
        fallback_chain=fallback or [],
        task_type=TaskType.SIMPLE,
        suitability_score=0.5,
        reason="test",
    )


class TestExecutingFallbackPipeline:
    async def test_execute_success_on_first_model(self) -> None:
        mock_exec = _MockExecutor({"openai/gpt-4o-mini": [_response("openai/gpt-4o-mini", "hello")]})
        pipeline = ExecutingFallbackPipeline(
            executor=mock_exec,  # type: ignore[arg-type]
            max_retries=0,
            base_backoff_seconds=0.0,
            max_backoff_seconds=0.0,
        )
        result = await pipeline.execute(_decision("openai/gpt-4o-mini"), "ping")
        assert result.succeeded
        assert result.model_used == "openai/gpt-4o-mini"
        assert result.response.content == "hello"

    async def test_execute_cascades_to_fallback_on_failure(self) -> None:
        mock_exec = _MockExecutor(
            {
                "openai/gpt-4o-mini": [ProviderError("openai/gpt-4o-mini", 500, "down")],
                "anthropic/claude-3.5-sonnet": [_response("anthropic/claude-3.5-sonnet", "fallback ok")],
            }
        )
        pipeline = ExecutingFallbackPipeline(
            executor=mock_exec,  # type: ignore[arg-type]
            max_retries=0,
            base_backoff_seconds=0.0,
            max_backoff_seconds=0.0,
        )
        result = await pipeline.execute(
            _decision("openai/gpt-4o-mini", ["anthropic/claude-3.5-sonnet"]), "ping"
        )
        assert result.succeeded
        assert result.model_used == "anthropic/claude-3.5-sonnet"

    async def test_execute_raises_when_all_exhausted(self) -> None:
        mock_exec = _MockExecutor(
            {
                "openai/gpt-4o-mini": [ProviderError("openai/gpt-4o-mini", 500, "down")],
                "anthropic/claude-3.5-sonnet": [
                    ProviderError("anthropic/claude-3.5-sonnet", 503, "unavailable")
                ],
            }
        )
        pipeline = ExecutingFallbackPipeline(
            executor=mock_exec,  # type: ignore[arg-type]
            max_retries=0,
            base_backoff_seconds=0.0,
            max_backoff_seconds=0.0,
        )
        with pytest.raises(AllCandidatesExhausted):
            await pipeline.execute(
                _decision("openai/gpt-4o-mini", ["anthropic/claude-3.5-sonnet"]), "ping"
            )
