"""Tests for ear.executor — LLMExecutor and ExecutingFallbackPipeline."""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ear.executor import (
    CompositeExecutingFallbackPipeline,
    CompositeExecutor,
    ExecutingFallbackPipeline,
    LLMExecutor,
    OllamaExecutor,
    _compute_cost,
)
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


# ── Helpers for Ollama tests ─────────────────────────────────────────────────

def _make_ollama_config(
    base_url: str = "http://localhost:11434",
    timeout: float = 30.0,
    max_retries: int = 3,
) -> Any:
    cfg = MagicMock()
    cfg.ear_ollama_base_url = base_url
    cfg.ear_request_timeout_seconds = timeout
    cfg.ear_max_retries = max_retries
    return cfg


def _ollama_success_payload(
    content: str = "hello from local",
    prompt_eval_count: int = 8,
    eval_count: int = 12,
) -> dict[str, Any]:
    return {
        "message": {"role": "assistant", "content": content},
        "prompt_eval_count": prompt_eval_count,
        "eval_count": eval_count,
    }


# ── TestOllamaExecutor ───────────────────────────────────────────────────────

class TestOllamaExecutor:
    @pytest.fixture()
    def executor(self) -> OllamaExecutor:
        return OllamaExecutor(_make_ollama_config())

    async def test_execute_success(self, executor: OllamaExecutor) -> None:
        payload = _ollama_success_payload(content="deep thought", prompt_eval_count=5, eval_count=7)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = payload

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await executor.execute("ollama/llama3", "what is 6 * 7?")

        assert isinstance(result, ExecutionResponse)
        assert result.model == "ollama/llama3"
        assert result.content == "deep thought"
        assert result.prompt_tokens == 5
        assert result.completion_tokens == 7
        assert result.total_tokens == 12

    async def test_execute_strips_ollama_prefix_in_api_call(self) -> None:
        """The bare model name (no prefix) must be sent to Ollama /api/chat."""
        payload = _ollama_success_payload()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = payload

        captured_payloads: list[dict[str, Any]] = []

        async def fake_post(url: str, **kwargs: Any) -> Any:
            captured_payloads.append(kwargs.get("json", {}))
            return mock_response

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = fake_post
            mock_client_cls.return_value = mock_client

            await OllamaExecutor(_make_ollama_config()).execute("ollama/llama3", "hello")

        assert captured_payloads[0]["model"] == "llama3"
        assert captured_payloads[0]["stream"] is False

    async def test_execute_raises_provider_error_on_4xx(self, executor: OllamaExecutor) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "model not found"

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            with pytest.raises(ProviderError) as exc_info:
                await executor.execute("ollama/llama3", "hello")

        assert exc_info.value.model_id == "ollama/llama3"
        assert exc_info.value.status_code == 404

    async def test_execute_raises_provider_error_on_5xx(self, executor: OllamaExecutor) -> None:
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
                await executor.execute("ollama/mistral", "hi")

        assert exc_info.value.status_code == 503

    async def test_execute_missing_token_counts_default_to_zero(self, executor: OllamaExecutor) -> None:
        payload = {"message": {"role": "assistant", "content": "ok"}}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = payload

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await executor.execute("ollama/llama3", "hello")

        assert result.prompt_tokens == 0
        assert result.completion_tokens == 0
        assert result.total_tokens == 0

    async def test_execute_trailing_slash_stripped_from_base_url(self) -> None:
        cfg = _make_ollama_config(base_url="http://localhost:11434/")
        executor = OllamaExecutor(cfg)

        payload = _ollama_success_payload()
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

            await executor.execute("ollama/llama3", "hello")

        assert captured_urls[0] == "http://localhost:11434/api/chat"


# ── TestCompositeExecutor ────────────────────────────────────────────────────

class TestCompositeExecutor:
    def _make_composite(
        self,
        openrouter_side_effect: Any = None,
        openrouter_return: ExecutionResponse | None = None,
        ollama_side_effect: Any = None,
        ollama_return: ExecutionResponse | None = None,
    ) -> CompositeExecutor:
        mock_openrouter = AsyncMock(spec=LLMExecutor)
        if openrouter_side_effect is not None:
            mock_openrouter.execute = AsyncMock(side_effect=openrouter_side_effect)
        elif openrouter_return is not None:
            mock_openrouter.execute = AsyncMock(return_value=openrouter_return)

        mock_ollama = AsyncMock(spec=OllamaExecutor)
        if ollama_side_effect is not None:
            mock_ollama.execute = AsyncMock(side_effect=ollama_side_effect)
        elif ollama_return is not None:
            mock_ollama.execute = AsyncMock(return_value=ollama_return)

        return CompositeExecutor(openrouter=mock_openrouter, ollama=mock_ollama)  # type: ignore[arg-type]

    async def test_ollama_prefix_routes_to_ollama_executor(self) -> None:
        ollama_resp = _response("ollama/llama3", "local answer")
        composite = self._make_composite(ollama_return=ollama_resp)

        result = await composite.execute("ollama/llama3", "hello")

        assert result.content == "local answer"
        composite._openrouter.execute.assert_not_called()  # type: ignore[attr-defined]
        composite._ollama.execute.assert_awaited_once_with("ollama/llama3", "hello")  # type: ignore[attr-defined]

    async def test_non_ollama_prefix_routes_to_openrouter_executor(self) -> None:
        openrouter_resp = _response("openai/gpt-4o-mini", "cloud answer")
        composite = self._make_composite(openrouter_return=openrouter_resp)

        result = await composite.execute("openai/gpt-4o-mini", "hello")

        assert result.content == "cloud answer"
        composite._ollama.execute.assert_not_called()  # type: ignore[attr-defined]
        composite._openrouter.execute.assert_awaited_once_with("openai/gpt-4o-mini", "hello")  # type: ignore[attr-defined]

    async def test_anthropic_routes_to_openrouter(self) -> None:
        openrouter_resp = _response("anthropic/claude-3-haiku", "haiku answer")
        composite = self._make_composite(openrouter_return=openrouter_resp)

        result = await composite.execute("anthropic/claude-3-haiku", "ping")

        assert result.content == "haiku answer"

    async def test_ollama_provider_error_propagates(self) -> None:
        composite = self._make_composite(
            ollama_side_effect=ProviderError("ollama/llama3", 503, "overloaded")
        )

        with pytest.raises(ProviderError) as exc_info:
            await composite.execute("ollama/llama3", "hello")

        assert exc_info.value.status_code == 503


# ── TestCompositeExecutingFallbackPipeline ───────────────────────────────────

class TestCompositeExecutingFallbackPipeline:
    async def test_execute_routes_ollama_model_via_composite(self) -> None:
        ollama_resp = _response("ollama/llama3", "private answer")
        mock_composite = MagicMock(spec=CompositeExecutor)
        mock_composite.execute = AsyncMock(return_value=ollama_resp)

        pipeline = CompositeExecutingFallbackPipeline(
            executor=mock_composite,
            max_retries=0,
            base_backoff_seconds=0.0,
            max_backoff_seconds=0.0,
        )

        result = await pipeline.execute(_decision("ollama/llama3"), "hello")

        assert result.succeeded
        assert result.model_used == "ollama/llama3"
        assert result.response.content == "private answer"

    async def test_execute_cascades_to_fallback_on_provider_error(self) -> None:
        ollama_err = ProviderError("ollama/llama3", 500, "crash")
        fallback_resp = _response("openai/gpt-4o-mini", "cloud fallback")
        responses: dict[str, list[Any]] = {
            "ollama/llama3": [ollama_err],
            "openai/gpt-4o-mini": [fallback_resp],
        }

        call_counts: dict[str, int] = {}

        async def dispatch(model_id: str, prompt: str) -> ExecutionResponse:
            queue = responses.get(model_id, [])
            if not queue:
                raise ProviderError(model_id, 500, "empty")
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item  # type: ignore[return-value]

        mock_composite = MagicMock(spec=CompositeExecutor)
        mock_composite.execute = dispatch  # type: ignore[method-assign]

        pipeline = CompositeExecutingFallbackPipeline(
            executor=mock_composite,
            max_retries=0,
            base_backoff_seconds=0.0,
            max_backoff_seconds=0.0,
        )

        result = await pipeline.execute(
            _decision("ollama/llama3", ["openai/gpt-4o-mini"]), "hello"
        )

        assert result.succeeded
        assert result.model_used == "openai/gpt-4o-mini"
