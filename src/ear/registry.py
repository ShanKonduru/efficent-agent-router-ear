"""Model registry — fetches and caches LLM specs from one or more model providers.

OOP Design
----------
``BaseModelRegistry``  — abstract contract every routing provider must satisfy.
``OpenRouterRegistry`` — concrete implementation for the OpenRouter API.
``RegistryFactory``    — creates registries by name; call :meth:`RegistryFactory.register`
                         to add a new provider (e.g. HuggingFace, Anthropic) without
                         touching any existing code (Open/Closed Principle).

``RegistryClient``     — backward-compatible alias for ``OpenRouterRegistry``.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from ear.config import EARConfig
from ear.models import LLMPricing, LLMSpec

logger = logging.getLogger(__name__)

_MODELS_PATH = "/models"


# ---------------------------------------------------------------------------
# Abstract base — the interface every provider must implement
# ---------------------------------------------------------------------------

class BaseModelRegistry(ABC):
    """Abstract base for all model-metadata providers.

    Implement this interface to add support for a new routing provider
    (e.g., HuggingFace Router, Anthropic Router) without modifying the
    routing engine, CLI, or any other layer.

    Extension recipe::

        class MyRegistry(BaseModelRegistry):
            @property
            def provider_name(self) -> str:
                return "myprovider"

            async def get_models(self) -> list[LLMSpec]:
                ...

            async def refresh(self) -> None:
                ...

        RegistryFactory.register("myprovider", MyRegistry)
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier (e.g. ``'openrouter'``)."""

    @abstractmethod
    async def get_models(self) -> list[LLMSpec]:
        """Return the list of available models, using cache when valid."""

    @abstractmethod
    async def refresh(self) -> None:
        """Force a live fetch and update the internal cache regardless of TTL."""


# ---------------------------------------------------------------------------
# Concrete implementation — OpenRouter
# ---------------------------------------------------------------------------

class OpenRouterRegistry(BaseModelRegistry):
    """Fetches live model metadata from OpenRouter with TTL-backed caching.

    On each :meth:`get_models` call the cache TTL is checked.  If expired a
    fresh fetch is attempted.  Should the fetch fail and a stale cache exists,
    the stale list is returned with a warning so the router can keep serving.
    """

    _PROVIDER: str = "openrouter"

    def __init__(self, config: EARConfig) -> None:
        self._config = config
        self._cache: list[LLMSpec] = []
        self._fetched_at: float = 0.0

    # ------------------------------------------------------------------
    # BaseModelRegistry interface
    # ------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        return self._PROVIDER

    async def get_models(self) -> list[LLMSpec]:
        """Return cached models, refreshing when TTL has expired.

        Returns a *copy* of the internal cache so callers cannot mutate state.
        """
        if not self._is_cache_valid():
            try:
                await self.refresh()
            except Exception as exc:
                if self._cache:
                    logger.warning(
                        "Registry refresh failed; serving stale cache. "
                        "provider=%s error=%r",
                        self.provider_name,
                        exc,
                    )
                else:
                    raise
        return list(self._cache)

    async def refresh(self) -> None:
        """Force a live fetch and replace the cache atomically."""
        models = await self._fetch_models()
        self._cache = models
        self._fetched_at = time.monotonic()
        logger.debug(
            "Registry cache refreshed. provider=%s model_count=%d",
            self.provider_name,
            len(models),
        )

    # ------------------------------------------------------------------
    # Internal helpers (protected — override in subclasses if needed)
    # ------------------------------------------------------------------

    async def _fetch_models(self) -> list[LLMSpec]:
        """Hit the provider's /models endpoint and return parsed specs."""
        url = self._config.ear_openrouter_base_url.rstrip("/") + _MODELS_PATH
        timeout = httpx.Timeout(float(self._config.ear_request_timeout_seconds))
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=self._build_headers())
            response.raise_for_status()
            payload: dict[str, Any] = response.json()

        raw_models: list[dict[str, Any]] = payload.get("data", [])
        specs: list[LLMSpec] = []
        for raw in raw_models:
            spec = self._parse_model(raw)
            if spec is not None:
                specs.append(spec)

        logger.debug(
            "Fetched %d raw models, parsed %d valid specs. provider=%s",
            len(raw_models),
            len(specs),
            self.provider_name,
        )
        return specs

    def _parse_model(self, raw: dict[str, Any]) -> LLMSpec | None:
        """Parse a single raw model dict; return ``None`` if required fields are missing.

        Parsing is intentionally lenient: malformed pricing is skipped (pricing
        becomes ``None``) rather than discarding the whole model entry.
        """
        model_id: Any = raw.get("id")
        context_length: Any = raw.get("context_length")

        # Fail-fast guard: required primitive fields must be present and sane.
        if not model_id or not isinstance(context_length, int) or context_length <= 0:
            logger.debug("Skipping malformed model entry: id=%r", model_id)
            return None

        pricing: LLMPricing | None = None
        raw_pricing = raw.get("pricing")
        if isinstance(raw_pricing, dict):
            try:
                prompt_cost = float(raw_pricing.get("prompt", 0))
                completion_cost = float(raw_pricing.get("completion", 0))
                pricing = LLMPricing(prompt=prompt_cost, completion=completion_cost)
            except (TypeError, ValueError):
                logger.debug("Could not parse pricing for model %r; omitting.", model_id)

        try:
            return LLMSpec(
                id=model_id,
                name=raw.get("name"),
                context_length=context_length,
                pricing=pricing,
            )
        except Exception:
            logger.debug(
                "LLMSpec validation failed for model %r; skipping.", model_id, exc_info=True
            )
            return None

    def _is_cache_valid(self) -> bool:
        """Return ``True`` if the cache is non-empty and still within TTL."""
        if not self._cache:
            return False
        age = time.monotonic() - self._fetched_at
        return age < self._config.ear_registry_ttl_seconds

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP request headers for the OpenRouter API."""
        return {
            "Authorization": f"Bearer {self._config.openrouter_api_key}",
            "HTTP-Referer": "https://github.com/ShanKonduru/efficent-agent-router-ear",
            "X-Title": "EAR — Efficient Agent Router",
        }


# ---------------------------------------------------------------------------
# Factory — extension point for new providers
# ---------------------------------------------------------------------------

class RegistryFactory:
    """Creates model registry instances by provider name.

    This is the primary extension point for adding new routing providers.
    No existing code needs to change — just register the new class and the
    factory will route :meth:`create` calls to it automatically.

    Example — adding a hypothetical HuggingFace provider::

        class HuggingFaceRegistry(BaseModelRegistry):
            ...

        RegistryFactory.register("huggingface", HuggingFaceRegistry)
        registry = RegistryFactory.create(config, provider="huggingface")
    """

    _PROVIDERS: dict[str, type[BaseModelRegistry]] = {
        "openrouter": OpenRouterRegistry,
    }

    @classmethod
    def create(cls, config: EARConfig, provider: str = "openrouter") -> BaseModelRegistry:
        """Instantiate and return a registry for the given *provider* name.

        Args:
            config: Runtime configuration (API keys, timeouts, etc.).
            provider: Case-insensitive provider key.  Defaults to ``"openrouter"``.

        Raises:
            ValueError: If *provider* is not registered.
        """
        key = provider.lower().strip()
        registry_class = cls._PROVIDERS.get(key)
        if registry_class is None:
            supported = ", ".join(sorted(cls._PROVIDERS))
            raise ValueError(
                f"Unknown provider '{provider}'. Supported providers: {supported}."
            )
        return registry_class(config)

    @classmethod
    def register(
        cls, provider: str, registry_class: type[BaseModelRegistry]
    ) -> None:
        """Register a new provider so it can be created via :meth:`create`.

        Args:
            provider: Case-insensitive provider name (e.g. ``"huggingface"``).
            registry_class: A concrete subclass of :class:`BaseModelRegistry`.

        Raises:
            TypeError: If *registry_class* is not a concrete subclass of
                :class:`BaseModelRegistry`.
        """
        if not (
            isinstance(registry_class, type)
            and issubclass(registry_class, BaseModelRegistry)
        ):
            raise TypeError(
                f"registry_class must be a subclass of BaseModelRegistry, "
                f"got {registry_class!r}."
            )
        cls._PROVIDERS[provider.lower().strip()] = registry_class

    @classmethod
    def supported_providers(cls) -> list[str]:
        """Return a sorted list of all registered provider names."""
        return sorted(cls._PROVIDERS)


# ---------------------------------------------------------------------------
# Backward-compatible alias
# ---------------------------------------------------------------------------

#: Alias retained for existing callers.  Prefer ``OpenRouterRegistry`` or
#: ``RegistryFactory.create()`` in new code.
RegistryClient = OpenRouterRegistry
