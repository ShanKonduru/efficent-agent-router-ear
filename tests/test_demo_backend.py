"""Tests for demo backend endpoints and deterministic replay behavior."""
from __future__ import annotations

from typing import Any

import pytest

from ear.demo_backend import (
    DEFAULT_REPLAY_SCENARIOS,
    DemoBackendService,
    DemoRouteRequest,
    _delta_percent,
    _LiveRouteResult,
)
from ear.models import BudgetPriority, TaskType


class TestDemoBackendService:
    async def test_list_scenarios_endpoint(self) -> None:
        service = DemoBackendService()
        payload = await service.list_scenarios_endpoint()

        assert "scenarios" in payload
        assert len(payload["scenarios"]) == len(DEFAULT_REPLAY_SCENARIOS)

    async def test_route_execute_replay_success(self) -> None:
        service = DemoBackendService()
        request = DemoRouteRequest(
            prompt="ignored in replay",
            replay_id="incident-response",
            execute=True,
        )

        payload = await service.route_execute_endpoint(request)
        assert payload["mode"] == "replay"
        assert payload["selected_model"] == "openai/gpt-4o-mini"
        assert payload["task_type"] == TaskType.PLANNING.value

    async def test_route_execute_replay_guardrails_blocked_path(self) -> None:
        service = DemoBackendService()
        request = DemoRouteRequest(
            prompt="ignored in replay",
            replay_id="security-jailbreak",
            execute=True,
        )

        payload = await service.route_execute_endpoint(request)
        assert payload["selected_model"] == "blocked-by-guardrails"
        assert "guardrails" in payload["response_text"].lower()

    async def test_route_execute_replay_not_found(self) -> None:
        service = DemoBackendService()
        request = DemoRouteRequest(prompt="x", replay_id="missing")

        payload = await service.route_execute_endpoint(request)
        assert payload["error"] == "scenario_not_found"

    async def test_route_execute_live_unavailable(self) -> None:
        service = DemoBackendService()
        payload = await service.route_execute_endpoint(DemoRouteRequest(prompt="x"))

        assert payload["error"] == "live_mode_unavailable"

    async def test_route_execute_live_runner(self) -> None:
        async def _live_runner(_request: DemoRouteRequest) -> _LiveRouteResult:
            return _LiveRouteResult(
                selected_model="openai/gpt-4o-mini",
                task_type=TaskType.SIMPLE,
                response_text="ok",
                estimated_cost_usd=0.001,
                latency_ms=100.0,
                fallback_trace=["openai/gpt-4o-mini"],
                reason="live",
            )

        service = DemoBackendService(live_runner=_live_runner)
        payload = await service.route_execute_endpoint(
            DemoRouteRequest(prompt="hello", budget_priority=BudgetPriority.LOW)
        )

        assert payload["mode"] == "live"
        assert payload["response_text"] == "ok"

    async def test_compare_endpoint(self) -> None:
        service = DemoBackendService()
        payload = await service.compare_endpoint("incident-response")

        assert payload["scenario_id"] == "incident-response"
        assert payload["baseline_cost_usd"] > payload["ear_cost_usd"]
        assert payload["cost_delta_pct"] > 0
        assert payload["latency_delta_pct"] > 0

    async def test_compare_not_found(self) -> None:
        service = DemoBackendService()
        payload = await service.compare_endpoint("missing")

        assert payload["error"] == "scenario_not_found"

    async def test_safety_feed_endpoint(self) -> None:
        service = DemoBackendService()
        payload = await service.safety_feed_endpoint(limit=5)

        expected_blocked = [
            s for s in DEFAULT_REPLAY_SCENARIOS if s.safety_incidents_blocked > 0
        ]
        assert "incidents" in payload
        assert len(payload["incidents"]) == min(5, len(expected_blocked))
        assert all(item["blocked"] is True for item in payload["incidents"])

    async def test_safety_feed_limit_clamped(self) -> None:
        service = DemoBackendService()
        payload = await service.safety_feed_endpoint(limit=-1)
        assert payload["incidents"] == []

    async def test_executive_summary_endpoint(self) -> None:
        service = DemoBackendService()
        payload = await service.executive_summary_endpoint()

        assert payload["scenarios_count"] == len(DEFAULT_REPLAY_SCENARIOS)
        assert payload["avg_cost_delta_pct"] > 0
        assert payload["avg_latency_delta_pct"] > 0
        assert payload["total_safety_incidents_blocked"] == sum(
            s.safety_incidents_blocked for s in DEFAULT_REPLAY_SCENARIOS
        )

    async def test_executive_summary_empty(self) -> None:
        service = DemoBackendService(scenarios=())
        payload = await service.executive_summary_endpoint()

        assert payload["scenarios_count"] == 0
        assert payload["avg_cost_delta_pct"] == 0.0
        assert payload["avg_latency_delta_pct"] == 0.0


def test_delta_percent() -> None:
    assert _delta_percent(100.0, 80.0) == 20.0
    assert _delta_percent(0.0, 10.0) == 0.0
