"""Tests for ear.cli - command wiring and current NotImplemented stubs."""
from __future__ import annotations

import runpy
import sys

import pytest

import ear.cli as cli_module
from ear.models import BudgetPriority


class TestCliModule:
    def test_app_is_defined(self) -> None:
        assert cli_module.app is not None

    def test_route_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            cli_module.route("hello", budget=BudgetPriority.MEDIUM)

    def test_inspect_models_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            cli_module.inspect_models(json_output=True)

    def test_stats_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError):
            cli_module.stats(json_output=False)

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
