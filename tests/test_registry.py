"""Tests for ear.registry - model metadata client, cache, and provider factory."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from ear.models import LLMSpec
from ear.registry import BaseModelRegistry, RegistryClient, RegistryFactory


class TestRegistryClientInit:
    def test_instantiation(self, config) -> None:  # type: ignore[no-untyped-def]
        client = RegistryClient(config)
        assert client is not None

    async def test_get_models_refreshes_on_empty_cache(self, config) -> None:  # type: ignore[no-untyped-def]
        client = RegistryClient(config)
        expected = [
            LLMSpec(id="openai/gpt-4o-mini", name="GPT-4o mini", context_length=16_000)
        ]
        fetch_mock = AsyncMock(return_value=expected)
        client._fetch_models = fetch_mock  # type: ignore[method-assign]

        got = await client.get_models()

        assert got == expected
        fetch_mock.assert_awaited_once()

    async def test_get_models_uses_valid_cache(self, config, sample_llm_spec) -> None:  # type: ignore[no-untyped-def]
        client = RegistryClient(config)
        client._cache = [sample_llm_spec]
        client._fetched_at = time.monotonic()

        fetch_mock = AsyncMock(return_value=[])
        client._fetch_models = fetch_mock  # type: ignore[method-assign]

        got = await client.get_models()

        assert got == [sample_llm_spec]
        fetch_mock.assert_not_called()

    async def test_get_models_returns_stale_cache_on_refresh_failure(
        self, config, sample_llm_spec
    ) -> None:  # type: ignore[no-untyped-def]
        client = RegistryClient(config)
        client._cache = [sample_llm_spec]
        # Use an explicit TTL-relative timestamp so cache is stale regardless of
        # the host monotonic clock origin (varies across CI runners).
        client._fetched_at = time.monotonic() - float(config.ear_registry_ttl_seconds) - 1.0

        fetch_mock = AsyncMock(side_effect=RuntimeError("provider down"))
        client._fetch_models = fetch_mock  # type: ignore[method-assign]

        got = await client.get_models()

        assert got == [sample_llm_spec]
        fetch_mock.assert_awaited_once()

    async def test_get_models_raises_when_no_cache_and_refresh_fails(
        self, config
    ) -> None:  # type: ignore[no-untyped-def]
        client = RegistryClient(config)
        fetch_mock = AsyncMock(side_effect=RuntimeError("provider down"))
        client._fetch_models = fetch_mock  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="provider down"):
            await client.get_models()

    def test_parse_model_skips_invalid_required_fields(self, config) -> None:  # type: ignore[no-untyped-def]
        client = RegistryClient(config)
        raw = {"id": "", "context_length": 0}

        assert client._parse_model(raw) is None

    def test_parse_model_handles_bad_pricing_but_keeps_model(self, config) -> None:  # type: ignore[no-untyped-def]
        client = RegistryClient(config)
        raw = {
            "id": "openai/gpt-4o",
            "name": "GPT-4o",
            "context_length": 128_000,
            "pricing": {"prompt": "nan-not-number", "completion": "0.2"},
        }

        parsed = client._parse_model(raw)

        assert parsed is not None
        assert parsed.id == "openai/gpt-4o"
        assert parsed.pricing is None

    def test_build_headers_are_ascii_safe(self, config) -> None:  # type: ignore[no-untyped-def]
        client = RegistryClient(config)
        headers = client._build_headers()

        assert headers["Authorization"].startswith("Bearer ")
        assert headers["X-Title"] == "EAR - Efficient Agent Router"
        # Enforce ASCII-safe header values for httpx request normalization.
        for value in headers.values():
            value.encode("ascii")

    async def test_fetch_models_parses_valid_entries(self, config) -> None:  # type: ignore[no-untyped-def]
        class _FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, list[dict[str, object]]]:
                return {
                    "data": [
                        {
                            "id": "openai/gpt-4o",
                            "name": "GPT-4o",
                            "context_length": 128_000,
                            "pricing": {"prompt": "0.1", "completion": "0.2"},
                        },
                        {
                            "id": "bad-model",
                            "name": "Bad",
                            "context_length": 0,
                        },
                    ]
                }

        class _FakeAsyncClient:
            def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
                self.called_url = ""
                self.called_headers: dict[str, str] = {}

            async def __aenter__(self) -> _FakeAsyncClient:
                return self

            async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
                return None

            async def get(self, url: str, headers: dict[str, str]) -> _FakeResponse:
                self.called_url = url
                self.called_headers = headers
                return _FakeResponse()

        import ear.registry as registry_module

        monkey = pytest.MonkeyPatch()
        monkey.setattr(registry_module.httpx, "AsyncClient", _FakeAsyncClient)
        try:
            client = RegistryClient(config)
            models = await client._fetch_models()
        finally:
            monkey.undo()

        assert len(models) == 1
        assert models[0].id == "openai/gpt-4o"

    def test_parse_model_returns_none_when_llmspec_validation_fails(self, config) -> None:  # type: ignore[no-untyped-def]
        client = RegistryClient(config)
        raw = {
            "id": ["not-a-string"],
            "name": "Broken",
            "context_length": 1024,
        }

        parsed = client._parse_model(raw)

        assert parsed is None


class TestRegistryFactory:
    class _DummyRegistry(BaseModelRegistry):
        def __init__(self, _config) -> None:  # type: ignore[no-untyped-def]
            self._models: list[LLMSpec] = []

        @property
        def provider_name(self) -> str:
            return "dummy"

        async def get_models(self) -> list[LLMSpec]:
            return list(self._models)

        async def refresh(self) -> None:
            self._models = []

    def test_create_default_provider(self, config) -> None:  # type: ignore[no-untyped-def]
        registry = RegistryFactory.create(config)

        assert isinstance(registry, RegistryClient)

    def test_create_unknown_provider_raises(self, config) -> None:  # type: ignore[no-untyped-def]
        with pytest.raises(ValueError, match="Unknown provider"):
            RegistryFactory.create(config, provider="unknown-provider")

    def test_register_and_create_custom_provider(self, config) -> None:  # type: ignore[no-untyped-def]
        RegistryFactory.register("dummy-provider", self._DummyRegistry)

        registry = RegistryFactory.create(config, provider="dummy-provider")

        assert isinstance(registry, self._DummyRegistry)

    def test_register_rejects_invalid_class(self) -> None:
        with pytest.raises(TypeError, match="subclass of BaseModelRegistry"):
            RegistryFactory.register("bad", int)  # type: ignore[arg-type]

    def test_supported_providers_includes_openrouter(self) -> None:
        supported = RegistryFactory.supported_providers()

        assert "openrouter" in supported
