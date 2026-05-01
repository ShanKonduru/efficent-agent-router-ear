"""Tests for ear.cli - command behavior and transport wiring."""
from __future__ import annotations

import runpy
import sys

import pytest
from typer.testing import CliRunner

import ear.cli as cli_module
from ear.metrics import get_metrics_collector
from ear.models import BudgetPriority, LLMPricing, LLMSpec


class _StubRegistry:
    def __init__(self, models: list[LLMSpec]) -> None:
        self._models = list(models)

    async def get_models(self) -> list[LLMSpec]:
        return list(self._models)


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


class TestCliModule:
    def setup_method(self) -> None:
        get_metrics_collector().reset()

    def test_app_is_defined(self) -> None:
        assert cli_module.app is not None

    def test_route_human_output(self, monkeypatch: pytest.MonkeyPatch, runner: CliRunner) -> None:
        models = [
            LLMSpec(
                id="openai/gpt-4o-mini",
                name="mini",
                context_length=16_000,
                pricing=LLMPricing(prompt=0.000001, completion=0.000002),
            )
        ]
        monkeypatch.setattr(cli_module, "get_config", lambda: object())
        monkeypatch.setattr(
            cli_module.RegistryFactory,
            "create",
            lambda _cfg: _StubRegistry(models),
        )

        result = runner.invoke(cli_module.app, ["route", "hello world"])

        assert result.exit_code == 0
        assert "Selected model" in result.stdout
        assert "openai/gpt-4o-mini" in result.stdout

    def test_route_json_output(self, monkeypatch: pytest.MonkeyPatch, runner: CliRunner) -> None:
        models = [
            LLMSpec(
                id="openai/gpt-4o-mini",
                name="mini",
                context_length=16_000,
                pricing=LLMPricing(prompt=0.000001, completion=0.000002),
            )
        ]
        monkeypatch.setattr(cli_module, "get_config", lambda: object())
        monkeypatch.setattr(
            cli_module.RegistryFactory,
            "create",
            lambda _cfg: _StubRegistry(models),
        )

        result = runner.invoke(cli_module.app, ["route", "hello world", "--json"])

        assert result.exit_code == 0
        assert '"selected_model": "openai/gpt-4o-mini"' in result.stdout

    def test_route_empty_prompt_fails(self, runner: CliRunner) -> None:
        result = runner.invoke(cli_module.app, ["route", "   "])
        assert result.exit_code != 0

    def test_inspect_models_json(self, monkeypatch: pytest.MonkeyPatch, runner: CliRunner) -> None:
        models = [
            LLMSpec(
                id="openai/gpt-4o-mini",
                name="mini",
                context_length=16_000,
                pricing=LLMPricing(prompt=0.000001, completion=0.000002),
            )
        ]
        monkeypatch.setattr(cli_module, "get_config", lambda: object())
        monkeypatch.setattr(
            cli_module.RegistryFactory,
            "create",
            lambda _cfg: _StubRegistry(models),
        )

        result = runner.invoke(cli_module.app, ["inspect-models", "--json"])

        assert result.exit_code == 0
        assert '"id": "openai/gpt-4o-mini"' in result.stdout

    def test_stats_human_output(self, runner: CliRunner) -> None:
        result = runner.invoke(cli_module.app, ["stats"])
        assert result.exit_code == 0
        assert "Total calls" in result.stdout

    def test_stats_json_output(self, runner: CliRunner) -> None:
        result = runner.invoke(cli_module.app, ["stats", "--json"])
        assert result.exit_code == 0
        assert '"total_calls"' in result.stdout

    def test_stats_lists_calls_by_model(self, runner: CliRunner) -> None:
        get_metrics_collector().record(
            cli_module.RouteMetric(
                model_id="openai/gpt-4o-mini",
                latency_ms=12.0,
                estimated_cost_usd=0.0,
                task_type=cli_module.TaskType.SIMPLE,
                success=True,
            )
        )

        result = runner.invoke(cli_module.app, ["stats"])

        assert result.exit_code == 0
        assert "Calls by model" in result.stdout
        assert "openai/gpt-4o-mini" in result.stdout

    def test_route_registry_failure_returns_error(
        self, monkeypatch: pytest.MonkeyPatch, runner: CliRunner
    ) -> None:
        class _FailingRegistry:
            async def get_models(self) -> list[LLMSpec]:
                raise RuntimeError("registry down")

        monkeypatch.setattr(cli_module, "get_config", lambda: object())
        monkeypatch.setattr(
            cli_module.RegistryFactory,
            "create",
            lambda _cfg: _FailingRegistry(),
        )

        result = runner.invoke(cli_module.app, ["route", "hello"])
        assert result.exit_code != 0

    def test_route_fails_when_no_models(self, monkeypatch: pytest.MonkeyPatch, runner: CliRunner) -> None:
        monkeypatch.setattr(cli_module, "get_config", lambda: object())
        monkeypatch.setattr(
            cli_module.RegistryFactory,
            "create",
            lambda _cfg: _StubRegistry([]),
        )

        result = runner.invoke(cli_module.app, ["route", "hello"])
        assert result.exit_code != 0

    def test_route_handles_router_value_error(
        self, monkeypatch: pytest.MonkeyPatch, runner: CliRunner
    ) -> None:
        models = [
            LLMSpec(
                id="openai/gpt-4o-mini",
                name="mini",
                context_length=16_000,
                pricing=LLMPricing(prompt=0.000001, completion=0.000002),
            )
        ]

        class _FailingRouter:
            def decide(self, request, available_models):  # type: ignore[no-untyped-def]
                raise ValueError("no eligible models")

        monkeypatch.setattr(cli_module, "get_config", lambda: object())
        monkeypatch.setattr(
            cli_module.RegistryFactory,
            "create",
            lambda _cfg: _StubRegistry(models),
        )
        monkeypatch.setattr(cli_module, "RouterEngine", lambda: _FailingRouter())

        result = runner.invoke(cli_module.app, ["route", "hello"])
        assert result.exit_code != 0

    def test_inspect_models_human_with_and_without_pricing(
        self, monkeypatch: pytest.MonkeyPatch, runner: CliRunner
    ) -> None:
        models = [
            LLMSpec(
                id="openai/gpt-4o-mini",
                name="mini",
                context_length=16_000,
                pricing=LLMPricing(prompt=0.000001, completion=0.000002),
            ),
            LLMSpec(
                id="openai/gpt-4.1",
                name="gpt-4.1",
                context_length=32_000,
                pricing=None,
            ),
        ]
        monkeypatch.setattr(cli_module, "get_config", lambda: object())
        monkeypatch.setattr(
            cli_module.RegistryFactory,
            "create",
            lambda _cfg: _StubRegistry(models),
        )

        result = runner.invoke(cli_module.app, ["inspect-models"])

        assert result.exit_code == 0
        assert "pricing=n/a" in result.stdout
        assert "openai/gpt-4o-mini" in result.stdout

    def test_inspect_models_human_empty(self, monkeypatch: pytest.MonkeyPatch, runner: CliRunner) -> None:
        monkeypatch.setattr(cli_module, "get_config", lambda: object())
        monkeypatch.setattr(
            cli_module.RegistryFactory,
            "create",
            lambda _cfg: _StubRegistry([]),
        )

        result = runner.invoke(cli_module.app, ["inspect-models"])

        assert result.exit_code == 0
        assert "No models available" in result.stdout

    def test_inspect_models_registry_failure(
        self, monkeypatch: pytest.MonkeyPatch, runner: CliRunner
    ) -> None:
        class _FailingRegistry:
            async def get_models(self) -> list[LLMSpec]:
                raise RuntimeError("down")

        monkeypatch.setattr(cli_module, "get_config", lambda: object())
        monkeypatch.setattr(
            cli_module.RegistryFactory,
            "create",
            lambda _cfg: _FailingRegistry(),
        )

        result = runner.invoke(cli_module.app, ["inspect-models"])
        assert result.exit_code != 0

    def test_main_delegates_to_app(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called = {"value": False}

        def _fake_app() -> None:
            called["value"] = True

        monkeypatch.setattr(cli_module, "app", _fake_app)

        cli_module.main()

        assert called["value"] is True

    def test_module_main_entrypoint_executes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "argv", ["ear"])

        # Ensure runpy executes a fresh module object to avoid RuntimeWarning
        # when warning filters are strict in CI.
        sys.modules.pop("ear.cli", None)

        with pytest.raises(SystemExit):
            runpy.run_module("ear.cli", run_name="__main__")
