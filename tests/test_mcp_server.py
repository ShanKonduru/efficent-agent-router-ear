"""Tests for ear.mcp_server — MCP service behavior and server bootstrap wiring."""
from __future__ import annotations

import json

import pytest

import ear.mcp_server as mcp_module
from ear.models import BudgetPriority, LLMPricing, LLMSpec


class _StubRegistry:
    def __init__(self, models: list[LLMSpec]) -> None:
        self._models = list(models)

    async def get_models(self) -> list[LLMSpec]:
        return list(self._models)


class TestEARMCPService:
    def test_model_stats_returns_summary_dict(self) -> None:
        service = mcp_module.EARMCPService()
        stats = service.model_stats()
        assert isinstance(stats, dict)
        assert "total_calls" in stats

    async def test_route_and_execute_returns_decision(self, monkeypatch: pytest.MonkeyPatch) -> None:
        models = [
            LLMSpec(
                id="openai/gpt-4o-mini",
                name="mini",
                context_length=16_000,
                pricing=LLMPricing(prompt=0.000001, completion=0.000002),
            )
        ]

        monkeypatch.setattr(mcp_module, "get_config", lambda: object())
        monkeypatch.setattr(
            mcp_module.RegistryFactory,
            "create",
            lambda _cfg: _StubRegistry(models),
        )

        service = mcp_module.EARMCPService()
        result = await service.route_and_execute(
            task_description="Summarize this",
            budget_priority=BudgetPriority.MEDIUM,
        )

        assert result["selected_model"] == "openai/gpt-4o-mini"
        assert "reason" in result
        assert isinstance(result["fallback_chain"], list)


class TestMCPServerBootstrap:
    def test_build_server_returns_fastmcp_instance(self) -> None:
        server = mcp_module._build_server()
        assert server is not None

    def test_session_stats_resource_returns_json(self) -> None:
        service = mcp_module.EARMCPService()
        payload = json.dumps(service.model_stats(), sort_keys=True)
        assert payload.startswith("{")
        assert "total_calls" in payload

    def test_serve_runs_stdio_transport(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called: dict[str, str] = {}

        class _StubServer:
            def run(self, transport: str = "stdio") -> None:
                called["transport"] = transport

        monkeypatch.setattr(mcp_module, "_build_server", lambda: _StubServer())

        import asyncio

        asyncio.run(mcp_module.serve())
        assert called["transport"] == "stdio"
