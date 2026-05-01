"""Tests for ear.registry — model metadata client and cache.

Stubs: full implementation tests added in M1 (E2).
"""
from __future__ import annotations

import pytest

from ear.registry import RegistryClient


class TestRegistryClientInit:
    def test_instantiation(self, config) -> None:  # type: ignore[no-untyped-def]
        client = RegistryClient(config)
        assert client is not None

    async def test_get_models_not_implemented(self, config) -> None:  # type: ignore[no-untyped-def]
        client = RegistryClient(config)
        with pytest.raises(NotImplementedError):
            await client.get_models()
