"""LLM execution adapter — calls OpenRouter chat completions and returns structured responses.

Design
------
``LLMExecutor``         - async provider-agnostic adapter that maps model IDs to
                          OpenRouter's chat/completions endpoint.
``ExecutingFallbackPipeline`` - ``FallbackPipeline`` subclass wired to a real
                          ``LLMExecutor`` so the cascade pipeline performs live
                          model calls instead of stubs.

Only httpx is required — no additional provider SDKs are needed because
OpenRouter exposes an OpenAI-compatible API.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from ear.config import EARConfig
from ear.fallback import FallbackPipeline, ProviderError
from ear.models import ExecutionResponse

logger = logging.getLogger(__name__)

_CHAT_COMPLETIONS_PATH = "/chat/completions"


def _compute_cost(
    pricing_prompt: float,
    pricing_completion: float,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Return estimated cost in USD given per-token pricing and usage."""
    return pricing_prompt * prompt_tokens + pricing_completion * completion_tokens


class LLMExecutor:
    """Sends a prompt to a specific model via OpenRouter and returns a structured response.

    The caller is responsible for error handling — this class raises
    ``ProviderError`` for HTTP errors and re-raises ``asyncio.TimeoutError``
    for timeout conditions so the ``FallbackPipeline`` can classify them
    correctly.
    """

    def __init__(self, config: EARConfig) -> None:
        self._base_url = config.ear_openrouter_base_url.rstrip("/")
        self._api_key = config.openrouter_api_key
        self._timeout = config.ear_request_timeout_seconds

    async def execute(self, model_id: str, prompt: str) -> ExecutionResponse:
        """Send *prompt* to *model_id* and return an ``ExecutionResponse``.

        Raises:
            ProviderError: HTTP 4xx/5xx from the provider.
            asyncio.TimeoutError: Request exceeded the configured timeout.
        """
        url = f"{self._base_url}{_CHAT_COMPLETIONS_PATH}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/ShanKonduru/efficient-agent-router-ear",
            "X-Title": "EAR Efficient Agent Router",
        }
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code >= 400:
            raise ProviderError(
                model_id=model_id,
                status_code=response.status_code,
                message=response.text[:200],
            )

        data = response.json()
        choices = data.get("choices") or [{}]
        choice = choices[0]
        content = choice.get("message", {}).get("content", "")
        usage: dict[str, Any] = data.get("usage", {})
        prompt_tokens: int = int(usage.get("prompt_tokens", 0))
        completion_tokens: int = int(usage.get("completion_tokens", 0))
        total_tokens: int = int(usage.get("total_tokens", prompt_tokens + completion_tokens))
        model_used: str = data.get("model", model_id)

        logger.info(
            "Executed model '%s'; tokens: prompt=%d completion=%d",
            model_used,
            prompt_tokens,
            completion_tokens,
        )

        return ExecutionResponse(
            model=model_used,
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )


class ExecutingFallbackPipeline(FallbackPipeline):
    """``FallbackPipeline`` that delegates ``_call_model`` to a real ``LLMExecutor``."""

    def __init__(self, executor: LLMExecutor, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._executor = executor

    async def _call_model(self, model_id: str, prompt: str) -> ExecutionResponse:
        """Invoke the real LLM and return the execution response."""
        return await self._executor.execute(model_id, prompt)
