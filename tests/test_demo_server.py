"""Tests for the local demo HTTP request router."""
from __future__ import annotations

import json
import threading
from unittest.mock import AsyncMock, MagicMock
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from ear.demo_backend import DemoBackendService
import ear.demo_server as demo_server_module
from ear.demo_server import DemoRequestRouter, _parse_int, create_handler, serve_demo_api
from ear.fallback import AllCandidatesExhausted
from ear.models import (
    BudgetPriority,
    ExecutionResponse,
    ExecutionResult,
    GuardrailResult,
    LLMPricing,
    LLMSpec,
    RoutingDecision,
    TaskType,
)
from ear.orchestrator import GuardrailsBlockedError


class _FakeLiveService:
    async def list_models_endpoint(self) -> dict:
        return {
            "models": [
                {
                    "id": "openai/gpt-4o-mini",
                    "name": "mini",
                    "context_length": 128000,
                    "trusted": False,
                    "pricing": {"prompt": 0.00000015, "completion": 0.0000006},
                }
            ]
        }

    async def stats_endpoint(self) -> dict:
        return {
            "total_calls": 1,
            "total_cost_usd": 0.001,
            "total_latency_ms": 10.0,
            "calls_by_model": {"openai/gpt-4o-mini": 1},
        }

    async def route_execute_endpoint(self, request) -> dict:  # type: ignore[no-untyped-def]
        return {
            "selected_model": "openai/gpt-4o-mini",
            "task_type": request.task_type.value if request.task_type else "simple",
            "budget_priority": request.budget_priority.value,
            "requested_model": request.preferred_model,
            "requested_model_applied": False,
            "response_text": "live answer",
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30,
            "estimated_cost_usd": 0.00002,
            "end_to_end_latency_ms": 100.0,
            "fallback_chain": ["anthropic/claude-3-haiku"],
            "fallback_trace": ["openai/gpt-4o-mini"],
            "reason": "Selected model based on score",
            "guardrails": {
                "passed": True,
                "injection_detected": False,
                "pii_detected": False,
                "risk_score": 0.0,
                "reason": None,
                "reason_codes": [],
            },
            "provider": "openrouter",
            "transparency_note": "EAR selected model based on policy.",
        }


class TestParseInt:
    def test_parse_valid(self) -> None:
        assert _parse_int("7", default=1) == 7

    def test_parse_invalid_returns_default(self) -> None:
        assert _parse_int("abc", default=3) == 3

    def test_parse_none_like_returns_default(self) -> None:
        assert _parse_int(None, default=4) == 4  # type: ignore[arg-type]


class TestLiveRouteRequest:
    def test_preferred_model_blank_rejected(self) -> None:
        with pytest.raises(ValueError):
            demo_server_module.LiveRouteRequest.model_validate(
                {
                    "prompt": "hello",
                    "preferred_model": "   ",
                }
            )


class TestLiveBackendService:
    @pytest.mark.asyncio
    async def test_list_models_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service = demo_server_module.LiveBackendService()

        models = [
            LLMSpec(
                id="openai/gpt-4o-mini",
                name="mini",
                context_length=128000,
                pricing=LLMPricing(prompt=0.1, completion=0.2),
                trusted=False,
            ),
            LLMSpec(
                id="ollama/llama3",
                name="llama3",
                context_length=8192,
                pricing=None,
                trusted=True,
            ),
        ]

        class _Registry:
            async def get_models(self) -> list[LLMSpec]:
                return models

        monkeypatch.setattr(demo_server_module, "get_config", lambda: object())
        monkeypatch.setattr(demo_server_module.RegistryFactory, "create", lambda _cfg: _Registry())

        payload = await service.list_models_endpoint()

        assert payload["models"][0]["id"] == "openai/gpt-4o-mini"
        assert payload["models"][0]["pricing"] == {"prompt": 0.1, "completion": 0.2}
        assert payload["models"][1]["pricing"] is None

    @pytest.mark.asyncio
    async def test_list_models_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service = demo_server_module.LiveBackendService()
        monkeypatch.setattr(demo_server_module, "get_config", lambda: object())
        monkeypatch.setattr(
            demo_server_module.RegistryFactory,
            "create",
            lambda _cfg: (_ for _ in ()).throw(RuntimeError("missing api key")),
        )

        payload = await service.list_models_endpoint()
        assert payload["error"] == "live_mode_unavailable"

    @pytest.mark.asyncio
    async def test_stats_endpoint(self) -> None:
        service = demo_server_module.LiveBackendService()
        payload = await service.stats_endpoint()
        assert "total_calls" in payload

    @pytest.mark.asyncio
    async def test_route_execute_live_mode_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service = demo_server_module.LiveBackendService()
        monkeypatch.setattr(
            demo_server_module,
            "get_config",
            lambda: (_ for _ in ()).throw(RuntimeError("config error")),
        )

        payload = await service.route_execute_endpoint(
            demo_server_module.LiveRouteRequest(prompt="hello")
        )
        assert payload["error"] == "live_mode_unavailable"

    @pytest.mark.asyncio
    async def test_route_execute_no_models(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service = demo_server_module.LiveBackendService()

        class _EmptyRegistry:
            async def get_models(self) -> list[LLMSpec]:
                return []

        monkeypatch.setattr(demo_server_module, "get_config", lambda: object())
        monkeypatch.setattr(demo_server_module.RegistryFactory, "create", lambda _cfg: _EmptyRegistry())

        payload = await service.route_execute_endpoint(
            demo_server_module.LiveRouteRequest(prompt="hello")
        )
        assert payload["error"] == "no_models_available"

    @pytest.mark.asyncio
    async def test_route_execute_live_mode_unavailable_network_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import httpx as _httpx

        service = demo_server_module.LiveBackendService()

        class _NetworkErrorRegistry:
            async def get_models(self) -> list:
                raise _httpx.ConnectError("All connection attempts failed")

        monkeypatch.setattr(demo_server_module, "get_config", lambda: object())
        monkeypatch.setattr(
            demo_server_module.RegistryFactory, "create", lambda _cfg: _NetworkErrorRegistry()
        )

        payload = await service.route_execute_endpoint(
            demo_server_module.LiveRouteRequest(prompt="hello")
        )
        assert payload["error"] == "live_mode_unavailable"
        assert "OpenRouter API" in payload["reason"]
        assert "ConnectError" in payload["reason"]

    @pytest.mark.asyncio
    async def test_route_execute_guardrails_blocked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service = demo_server_module.LiveBackendService()
        models = [
            LLMSpec(
                id="openai/gpt-4o-mini",
                name="mini",
                context_length=128000,
                pricing=LLMPricing(prompt=0.1, completion=0.2),
            )
        ]

        class _Registry:
            async def get_models(self) -> list[LLMSpec]:
                return models

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(side_effect=GuardrailsBlockedError("blocked"))

        monkeypatch.setattr(demo_server_module, "get_config", lambda: object())
        monkeypatch.setattr(demo_server_module.RegistryFactory, "create", lambda _cfg: _Registry())
        monkeypatch.setattr(demo_server_module.ExecutionOrchestrator, "from_config", lambda _cfg: mock_orch)

        payload = await service.route_execute_endpoint(
            demo_server_module.LiveRouteRequest(prompt="hello", execute=True)
        )
        assert payload["error"] == "guardrails_blocked"

    @pytest.mark.asyncio
    async def test_route_execute_all_candidates_exhausted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service = demo_server_module.LiveBackendService()
        models = [
            LLMSpec(
                id="openai/gpt-4o-mini",
                name="mini",
                context_length=128000,
                pricing=LLMPricing(prompt=0.1, completion=0.2),
            )
        ]

        class _Registry:
            async def get_models(self) -> list[LLMSpec]:
                return models

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(side_effect=AllCandidatesExhausted(["openai/gpt-4o-mini"]))

        monkeypatch.setattr(demo_server_module, "get_config", lambda: object())
        monkeypatch.setattr(demo_server_module.RegistryFactory, "create", lambda _cfg: _Registry())
        monkeypatch.setattr(demo_server_module.ExecutionOrchestrator, "from_config", lambda _cfg: mock_orch)

        payload = await service.route_execute_endpoint(
            demo_server_module.LiveRouteRequest(prompt="hello", execute=True)
        )
        assert payload["error"] == "all_candidates_exhausted"

    @pytest.mark.asyncio
    async def test_route_execute_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service = demo_server_module.LiveBackendService()
        models = [
            LLMSpec(
                id="ollama/llama3",
                name="llama3",
                context_length=8192,
                pricing=LLMPricing(prompt=0.0, completion=0.0),
                trusted=True,
            )
        ]

        class _Registry:
            async def get_models(self) -> list[LLMSpec]:
                return models

        result = ExecutionResult(
            decision=RoutingDecision(
                selected_model="ollama/llama3",
                fallback_chain=[],
                task_type=TaskType.SIMPLE,
                suitability_score=0.7,
                reason="selected",
            ),
            response=ExecutionResponse(
                model="ollama/llama3",
                content="safe answer",
                prompt_tokens=4,
                completion_tokens=6,
                total_tokens=10,
            ),
            fallback_trace=["ollama/llama3"],
            end_to_end_latency_ms=50.0,
            estimated_cost_usd=0.0,
            guardrail_result=GuardrailResult(
                passed=False,
                injection_detected=True,
                pii_detected=False,
                reason="blocked",
                risk_score=0.9,
            ),
        )

        mock_orch = MagicMock()
        mock_orch.run = AsyncMock(return_value=result)

        monkeypatch.setattr(demo_server_module, "get_config", lambda: object())
        monkeypatch.setattr(demo_server_module.RegistryFactory, "create", lambda _cfg: _Registry())
        monkeypatch.setattr(demo_server_module.ExecutionOrchestrator, "from_config", lambda _cfg: mock_orch)

        payload = await service.route_execute_endpoint(
            demo_server_module.LiveRouteRequest(
                prompt="hello",
                budget_priority=BudgetPriority.MEDIUM,
                preferred_model="openai/gpt-4o-mini",
                execute=True,
            )
        )
        assert payload["selected_model"] == "ollama/llama3"
        assert payload["provider"] == "ollama"
        assert payload["requested_model"] == "openai/gpt-4o-mini"
        assert payload["requested_model_applied"] is False

    @pytest.mark.asyncio
    async def test_route_execute_route_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        service = demo_server_module.LiveBackendService()
        models = [
            LLMSpec(
                id="openai/gpt-4o-mini",
                name="mini",
                context_length=128000,
                pricing=LLMPricing(prompt=0.1, completion=0.2),
            )
        ]

        class _Registry:
            async def get_models(self) -> list[LLMSpec]:
                return models

        decision = RoutingDecision(
            selected_model="openai/gpt-4o-mini",
            fallback_chain=[],
            task_type=TaskType.SIMPLE,
            suitability_score=0.5,
            reason="route-only",
        )

        monkeypatch.setattr(demo_server_module, "get_config", lambda: object())
        monkeypatch.setattr(demo_server_module.RegistryFactory, "create", lambda _cfg: _Registry())
        monkeypatch.setattr(
            demo_server_module.RouterEngine,
            "decide",
            lambda self, _request, _models: decision,
        )

        payload = await service.route_execute_endpoint(
            demo_server_module.LiveRouteRequest(prompt="hello", execute=False)
        )
        assert payload["selected_model"] == "openai/gpt-4o-mini"
        assert payload["response_text"] == ""


class TestTransparencyNote:
    def test_guardrail_shift_to_ollama_message(self) -> None:
        note = demo_server_module._build_transparency_note(
            selected_model="ollama/llama3",
            requested_model=None,
            decision_reason="r",
            guardrail={"passed": False, "pii_detected": False},
        )
        assert "shifted execution to Ollama" in note

    def test_pii_routed_to_ollama_message(self) -> None:
        note = demo_server_module._build_transparency_note(
            selected_model="ollama/llama3",
            requested_model=None,
            decision_reason="r",
            guardrail={"passed": True, "pii_detected": True},
        )
        assert "PII safeguards" in note

    def test_requested_model_overridden_message(self) -> None:
        note = demo_server_module._build_transparency_note(
            selected_model="openai/gpt-4o-mini",
            requested_model="openai/gpt-4o",
            decision_reason="score",
            guardrail={"passed": True, "pii_detected": False},
        )
        assert "You requested" in note

    def test_requested_model_applied_message(self) -> None:
        note = demo_server_module._build_transparency_note(
            selected_model="openai/gpt-4o-mini",
            requested_model="openai/gpt-4o-mini",
            decision_reason="score",
            guardrail={"passed": True, "pii_detected": False},
        )
        assert "Requested model was selected" in note

    def test_default_transparency_message(self) -> None:
        note = demo_server_module._build_transparency_note(
            selected_model="openai/gpt-4o-mini",
            requested_model=None,
            decision_reason="score",
            guardrail={"passed": True, "pii_detected": False},
        )
        assert "EAR selected" in note


class TestDemoRequestRouter:
    def setup_method(self) -> None:
        self.router = DemoRequestRouter(live_service=_FakeLiveService())

    def test_get_scenarios(self) -> None:
        status, payload = self.router.handle_request("GET", "/demo/scenarios")
        assert status == 200
        assert "scenarios" in payload
        assert len(payload["scenarios"]) > 0

    def test_get_summary(self) -> None:
        status, payload = self.router.handle_request("GET", "/demo/summary")
        assert status == 200
        assert payload["scenarios_count"] > 0

    def test_get_safety_feed(self) -> None:
        status, payload = self.router.handle_request("GET", "/demo/safety-feed?limit=1")
        assert status == 200
        assert len(payload["incidents"]) <= 1

    def test_get_compare(self) -> None:
        status, payload = self.router.handle_request(
            "GET", "/demo/compare?scenario_id=incident-response"
        )
        assert status == 200
        assert payload["scenario_id"] == "incident-response"

    def test_get_compare_ollama_mode(self) -> None:
        status, payload = self.router.handle_request(
            "GET", "/demo/compare?scenario_id=security-jailbreak&mode=ollama"
        )
        assert status == 200
        assert payload["ear_model"] == "ollama/llama3"

    def test_get_scenarios_ollama_mode(self) -> None:
        status, payload = self.router.handle_request("GET", "/demo/scenarios?mode=ollama")
        assert status == 200
        attack_models = {
            s["ear_model"]
            for s in payload["scenarios"]
            if s["id"] in ("security-jailbreak", "policy-exfiltration", "credential-harvest")
        }
        assert attack_models == {"ollama/llama3"}

    def test_get_compare_missing_scenario_id(self) -> None:
        status, payload = self.router.handle_request("GET", "/demo/compare")
        assert status == 400
        assert payload["error"] == "missing_scenario_id"

    def test_get_compare_not_found(self) -> None:
        status, payload = self.router.handle_request(
            "GET", "/demo/compare?scenario_id=missing"
        )
        assert status == 404
        assert payload["error"] == "scenario_not_found"

    def test_post_route_execute(self) -> None:
        body = json.dumps({
            "prompt": "hello",
            "replay_id": "incident-response",
            "execute": True,
        })
        status, payload = self.router.handle_request(
            "POST", "/demo/route-execute", body
        )
        assert status == 200
        assert payload["mode"] == "replay"

    def test_post_route_execute_invalid_json(self) -> None:
        status, payload = self.router.handle_request(
            "POST", "/demo/route-execute", "{not-json"
        )
        assert status == 400
        assert payload["error"] == "invalid_json"

    def test_post_route_execute_invalid_request(self) -> None:
        body = json.dumps({"prompt": ""})
        status, payload = self.router.handle_request(
            "POST", "/demo/route-execute", body
        )
        assert status == 400
        assert payload["error"] == "invalid_request"

    def test_post_route_execute_missing_body(self) -> None:
        status, payload = self.router.handle_request(
            "POST", "/demo/route-execute", None
        )
        assert status == 400
        assert payload["error"] == "missing_body"

    def test_not_found(self) -> None:
        status, payload = self.router.handle_request("GET", "/unknown")
        assert status == 404
        assert payload["error"] == "not_found"

    def test_get_live_models(self) -> None:
        status, payload = self.router.handle_request("GET", "/live/models")
        assert status == 200
        assert payload["models"][0]["id"] == "openai/gpt-4o-mini"

    def test_get_live_stats(self) -> None:
        status, payload = self.router.handle_request("GET", "/live/stats")
        assert status == 200
        assert payload["total_calls"] == 1

    def test_post_live_route_execute(self) -> None:
        body = json.dumps(
            {
                "prompt": "hello",
                "task_type": "simple",
                "budget_priority": "medium",
                "preferred_model": "openai/gpt-4o",
                "execute": True,
            }
        )
        status, payload = self.router.handle_request("POST", "/live/route-execute", body)
        assert status == 200
        assert payload["response_text"] == "live answer"
        assert payload["requested_model"] == "openai/gpt-4o"

    def test_post_live_route_execute_invalid_json(self) -> None:
        status, payload = self.router.handle_request("POST", "/live/route-execute", "{bad-json")
        assert status == 400
        assert payload["error"] == "invalid_json"

    def test_post_live_route_execute_invalid_request(self) -> None:
        body = json.dumps({"prompt": ""})
        status, payload = self.router.handle_request("POST", "/live/route-execute", body)
        assert status == 400
        assert payload["error"] == "invalid_request"

    def test_post_live_route_execute_missing_body(self) -> None:
        status, payload = self.router.handle_request("POST", "/live/route-execute", None)
        assert status == 400
        assert payload["error"] == "missing_body"

    def test_get_live_models_unavailable(self) -> None:
        class _UnavailableLive:
            async def list_models_endpoint(self) -> dict:
                return {"error": "live_mode_unavailable", "reason": "missing key"}

            async def stats_endpoint(self) -> dict:
                return {}

            async def route_execute_endpoint(self, request) -> dict:  # type: ignore[no-untyped-def]
                return {}

        router = DemoRequestRouter(live_service=_UnavailableLive())
        status, payload = router.handle_request("GET", "/live/models")
        assert status == 503
        assert payload["error"] == "live_mode_unavailable"


class TestDemoHttpHandler:
    def test_live_get_and_post_requests(self) -> None:
        router = DemoRequestRouter(live_service=_FakeLiveService())
        handler = create_handler(router)
        server = demo_server_module.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            base_url = f"http://127.0.0.1:{server.server_port}"

            with urlopen(f"{base_url}/") as response:
                html = response.read().decode("utf-8")
                assert "<!doctype html>" in html.lower()
                assert "EAR LLM Explorer" in html
                assert response.headers["Content-Type"].startswith("text/html")

            with urlopen(f"{base_url}/demo/scenarios") as response:
                payload = json.loads(response.read().decode("utf-8"))
                assert "scenarios" in payload
                assert response.headers["Access-Control-Allow-Origin"] == "*"

            body = json.dumps(
                {
                    "prompt": "hello",
                    "replay_id": "incident-response",
                    "execute": True,
                }
            ).encode("utf-8")
            request = Request(
                f"{base_url}/demo/route-execute",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request) as response:
                payload = json.loads(response.read().decode("utf-8"))
                assert payload["mode"] == "replay"

            with pytest.raises(HTTPError) as exc_info:
                urlopen(f"{base_url}/demo/compare")
            assert exc_info.value.code == 400

            with urlopen(f"{base_url}/live/models") as response:
                payload = json.loads(response.read().decode("utf-8"))
                assert payload["models"][0]["id"] == "openai/gpt-4o-mini"

            options_request = Request(
                f"{base_url}/live/route-execute",
                method="OPTIONS",
            )
            with urlopen(options_request) as response:
                assert response.status == 204
                assert response.headers["Access-Control-Allow-Methods"] == "GET, POST, OPTIONS"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_send_json_ignores_client_disconnect(self) -> None:
        router = DemoRequestRouter(live_service=_FakeLiveService())
        handler_class = create_handler(router)

        class _FakeWriter:
            def write(self, _data: bytes) -> None:
                return

        class _FakeHandler:
            def __init__(self) -> None:
                self.wfile = _FakeWriter()

            def send_response(self, _status: int) -> None:
                return

            def send_header(self, _name: str, _value: str) -> None:
                return

            def _send_cors_headers(self) -> None:
                return

            def end_headers(self) -> None:
                raise ConnectionResetError("client disconnected")

        fake_handler = _FakeHandler()

        handler_class._write_response(
            fake_handler,
            status=200,
            content_type="application/json",
            response=b'{"ok": true}',
        )


class TestServeDemoApi:
    def test_serve_demo_api_invokes_server(self, monkeypatch: pytest.MonkeyPatch) -> None:
        events: dict[str, object] = {}

        class _FakeServer:
            def __init__(self, address, handler):  # type: ignore[no-untyped-def]
                events["address"] = address
                events["handler"] = handler

            def __enter__(self):
                events["entered"] = True
                return self

            def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
                events["exited"] = True
                return False

            def serve_forever(self) -> None:
                events["served"] = True

        monkeypatch.setattr(demo_server_module, "ThreadingHTTPServer", _FakeServer)

        serve_demo_api(host="127.0.0.1", port=8099)

        assert events["address"] == ("127.0.0.1", 8099)
        assert events["entered"] is True
        assert events["served"] is True
        assert events["exited"] is True
