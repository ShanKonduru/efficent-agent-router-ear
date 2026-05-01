"""Model registry — fetches and caches LLM specs from OpenRouter."""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from ear.config import EARConfig
from ear.models import LLMPricing, LLMSpec

logger = logging.getLogger(__name__)

_MODELS_PATH = "/models"


class RegistryClient:
    """Fetches live model metadata from OpenRouter and serves a TTL-backed cache."""

    def __init__(self, config: EARConfig) -> None:
        self._config = config
        self._cache: list[LLMSpec] = []
        self._fetched_at: float = 0.0

    async def get_models(self) -> list[LLMSpec]:
        """Return cached models, refreshing if the TTL has expired.

        On refresh failure the stale cache is returned with a warning.
        """
        raise NotImplementedError

    async def _fetch_models(self) -> list[LLMSpec]:
        """Hit the OpenRouter /models endpoint and parse the response."""
        raise NotImplementedError

    def _parse_model(self, raw: dict[str, Any]) -> LLMSpec | None:
        """Parse a single raw model dict; return None if required fields are missing."""
        raise NotImplementedError

    def _is_cache_valid(self) -> bool:
        """Return True if the cached data is still within TTL."""
        raise NotImplementedError

    def _build_headers(self) -> dict[str, str]:
        """Build HTTP headers for OpenRouter requests."""
        raise NotImplementedError
