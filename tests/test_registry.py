"""Tests for ear.registry - model metadata client, cache, and provider factory."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from ear.models import LLMSpec
from ear.registry import BaseModelRegistry, OllamaRegistry, RegistryClient, RegistryFactory


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

    def test_supported_providers_includes_ollama(self) -> None:
        supported = RegistryFactory.supported_providers()

        assert "ollama" in supported

    def test_create_ollama_provider(self, config) -> None:  # type: ignore[no-untyped-def]
        registry = RegistryFactory.create(config, provider="ollama")

        assert isinstance(registry, OllamaRegistry)


# ── TestOllamaRegistry ────────────────────────────────────────────────────────

class _FakeOllamaResponse:
    def __init__(self, models: list[dict], status_code: int = 200) -> None:
        self._models = models
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return {"models": self._models}


def _fake_ollama_client(response: _FakeOllamaResponse):  # type: ignore[no-untyped-def]
    """Return a context-manager-compatible async HTTP client that returns *response*."""
    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            pass

        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, *args) -> None:  # type: ignore[no-untyped-def]
            pass

        async def get(self, url: str) -> _FakeOllamaResponse:
            return response

    return _FakeClient


class TestOllamaRegistry:
    async def test_get_models_returns_trusted_specs(self, config, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Parsed models should have ollama/ prefix and trusted=True."""
        import ear.registry as registry_module

        fake_resp = _FakeOllamaResponse(
            [
                {"name": "llama3"},
                {"name": "mistral"},
            ]
        )
        monkeypatch.setattr(registry_module.httpx, "AsyncClient", _fake_ollama_client(fake_resp))
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        from ear.config import EARConfig

        cfg = EARConfig()  # type: ignore[call-arg]
        registry = OllamaRegistry(cfg)
        models = await registry.get_models()

        ids = [m.id for m in models]
        assert "ollama/llama3" in ids
        assert "ollama/mistral" in ids
        for m in models:
            assert m.trusted is True
            assert m.pricing is not None
            assert m.pricing.prompt == 0.0
            assert m.pricing.completion == 0.0

    async def test_get_models_skips_entry_with_missing_name(self, config, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        import ear.registry as registry_module

        fake_resp = _FakeOllamaResponse(
            [
                {"name": "llama3"},
                {},  # missing name — should be skipped
                {"name": ""},  # empty name — should be skipped
            ]
        )
        monkeypatch.setattr(registry_module.httpx, "AsyncClient", _fake_ollama_client(fake_resp))
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        from ear.config import EARConfig

        cfg = EARConfig()  # type: ignore[call-arg]
        registry = OllamaRegistry(cfg)
        models = await registry.get_models()

        assert len(models) == 1
        assert models[0].id == "ollama/llama3"

    async def test_get_models_defaults_context_length_when_missing(self, config, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        import ear.registry as registry_module

        fake_resp = _FakeOllamaResponse([{"name": "phi3"}])
        monkeypatch.setattr(registry_module.httpx, "AsyncClient", _fake_ollama_client(fake_resp))
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        from ear.config import EARConfig

        cfg = EARConfig()  # type: ignore[call-arg]
        registry = OllamaRegistry(cfg)
        models = await registry.get_models()

        assert models[0].context_length == 8_192  # _OLLAMA_DEFAULT_CONTEXT_LENGTH

    async def test_get_models_defaults_context_length_when_zero(self, config, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        import ear.registry as registry_module

        fake_resp = _FakeOllamaResponse([{"name": "phi3", "context_length": 0}])
        monkeypatch.setattr(registry_module.httpx, "AsyncClient", _fake_ollama_client(fake_resp))
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        from ear.config import EARConfig

        cfg = EARConfig()  # type: ignore[call-arg]
        registry = OllamaRegistry(cfg)
        models = await registry.get_models()

        assert models[0].context_length == 8_192

    async def test_get_models_uses_valid_cache(self, config, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Second call within TTL must not hit the network."""
        import ear.registry as registry_module

        fake_resp = _FakeOllamaResponse([{"name": "llama3"}])
        mock_client_cls = _fake_ollama_client(fake_resp)
        monkeypatch.setattr(registry_module.httpx, "AsyncClient", mock_client_cls)
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        from ear.config import EARConfig

        cfg = EARConfig()  # type: ignore[call-arg]
        registry = OllamaRegistry(cfg)
        await registry.get_models()  # first call — populates cache

        # Patch _fetch_models to detect any second network call
        fetch_mock = AsyncMock(return_value=[])
        registry._fetch_models = fetch_mock  # type: ignore[method-assign]

        second = await registry.get_models()

        fetch_mock.assert_not_called()
        assert len(second) == 1

    async def test_get_models_serves_stale_cache_on_refresh_failure(self, config, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        import ear.registry as registry_module

        fake_resp = _FakeOllamaResponse([{"name": "llama3"}])
        monkeypatch.setattr(registry_module.httpx, "AsyncClient", _fake_ollama_client(fake_resp))
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        from ear.config import EARConfig

        cfg = EARConfig()  # type: ignore[call-arg]
        registry = OllamaRegistry(cfg)
        await registry.get_models()  # fill cache

        # Force cache expiry
        registry._fetched_at = time.monotonic() - float(cfg.ear_registry_ttl_seconds) - 1.0
        # Make refresh fail
        registry._fetch_models = AsyncMock(side_effect=RuntimeError("ollama offline"))  # type: ignore[method-assign]

        result = await registry.get_models()

        assert len(result) == 1
        assert result[0].id == "ollama/llama3"

    async def test_get_models_raises_when_no_cache_and_refresh_fails(self, config, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        from ear.config import EARConfig

        cfg = EARConfig()  # type: ignore[call-arg]
        registry = OllamaRegistry(cfg)
        registry._fetch_models = AsyncMock(side_effect=RuntimeError("ollama offline"))  # type: ignore[method-assign]

        with pytest.raises(RuntimeError, match="ollama offline"):
            await registry.get_models()

    def test_provider_name_is_ollama(self, config) -> None:  # type: ignore[no-untyped-def]
        from ear.config import EARConfig

        cfg = EARConfig()  # type: ignore[call-arg]
        registry = OllamaRegistry(cfg)

        assert registry.provider_name == "ollama"

    def test_parse_model_returns_none_when_llmspec_raises(self, config, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """_parse_model() must return None and not propagate when LLMSpec() raises."""
        import ear.registry as registry_module
        from ear.config import EARConfig

        cfg = EARConfig()  # type: ignore[call-arg]
        registry = OllamaRegistry(cfg)

        # Force LLMSpec constructor to raise so the except branch is exercised.
        monkeypatch.setattr(registry_module, "LLMSpec", MagicMock(side_effect=ValueError("bad spec")))

        result = registry._parse_model({"name": "llama3"})

        assert result is None
