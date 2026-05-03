"""Local HTTP server for EAR leadership demo endpoints."""
from __future__ import annotations

import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

import httpx

from pydantic import BaseModel, Field, field_validator

from ear.config import get_config
from ear.fallback import AllCandidatesExhausted
from ear.demo_backend import DemoBackendService, DemoRouteRequest, OLLAMA_REPLAY_SCENARIOS
from ear.metrics import get_metrics_collector
from ear.models import BudgetPriority, ControllerHint, RoutingRequest, TaskType
from ear.orchestrator import ExecutionOrchestrator, GuardrailsBlockedError
from ear.registry import RegistryFactory
from ear.router_engine import RouterEngine


_DEMO_HTML_PATH = Path(__file__).resolve().parents[2] / "docs" / "llm_explorer.html"

_SERVICES: dict[str, DemoBackendService] = {
    "standard": DemoBackendService(),
    "ollama": DemoBackendService(scenarios=OLLAMA_REPLAY_SCENARIOS),
}


class LiveRouteRequest(BaseModel):
    """Request payload for live route-and-execute endpoint."""

    prompt: str = Field(..., min_length=1)
    task_type: TaskType | None = None
    budget_priority: BudgetPriority = BudgetPriority.MEDIUM
    preferred_model: str | None = None
    execute: bool = True

    @field_validator("preferred_model")
    @classmethod
    def preferred_model_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("preferred_model must not be blank")
        return value


class LiveBackendService:
    """Service layer for live EAR endpoints used by the React UI."""

    async def list_models_endpoint(self) -> dict[str, Any]:
        try:
            config = get_config()
            registry = RegistryFactory.create(config)
            models = await registry.get_models()
        except Exception as exc:
            return {
                "error": "live_mode_unavailable",
                "reason": str(exc),
            }

        return {
            "models": [
                {
                    "id": model.id,
                    "name": model.name,
                    "context_length": model.context_length,
                    "trusted": model.trusted,
                    "pricing": (
                        {
                            "prompt": model.pricing.prompt,
                            "completion": model.pricing.completion,
                        }
                        if model.pricing is not None
                        else None
                    ),
                }
                for model in models
            ]
        }

    async def stats_endpoint(self) -> dict[str, Any]:
        return get_metrics_collector().summary().model_dump(mode="json")

    async def route_execute_endpoint(self, request: LiveRouteRequest) -> dict[str, Any]:
        try:
            config = get_config()
            registry = RegistryFactory.create(config)
            models = await registry.get_models()
        except httpx.NetworkError as exc:
            return {
                "error": "live_mode_unavailable",
                "reason": (
                    f"Cannot reach the OpenRouter API ({type(exc).__name__}). "
                    "Check your network connection and OPENROUTER_API_KEY, then retry."
                ),
            }
        except Exception as exc:
            return {
                "error": "live_mode_unavailable",
                "reason": str(exc),
            }

        if not models:
            return {
                "error": "no_models_available",
                "reason": "No models available from registry.",
            }

        hint = (
            ControllerHint(
                preferred_model=request.preferred_model,
                confidence=1.0,
            )
            if request.preferred_model
            else None
        )
        routing_request = RoutingRequest(
            prompt=request.prompt,
            task_type=request.task_type,
            budget_priority=request.budget_priority,
            controller_hint=hint,
        )

        if request.execute:
            orchestrator = ExecutionOrchestrator.from_config(config)
            try:
                result = await orchestrator.run(routing_request, models)
            except GuardrailsBlockedError as exc:
                return {
                    "error": "guardrails_blocked",
                    "reason": exc.reason,
                }
            except AllCandidatesExhausted as exc:
                return {
                    "error": "all_candidates_exhausted",
                    "reason": str(exc),
                }

            selected_model = result.response.model
            return {
                "selected_model": selected_model,
                "task_type": result.decision.task_type.value,
                "budget_priority": request.budget_priority.value,
                "requested_model": request.preferred_model,
                "requested_model_applied": bool(
                    request.preferred_model and request.preferred_model == selected_model
                ),
                "response_text": result.response.content,
                "prompt_tokens": result.response.prompt_tokens,
                "completion_tokens": result.response.completion_tokens,
                "total_tokens": result.response.total_tokens,
                "estimated_cost_usd": result.estimated_cost_usd,
                "end_to_end_latency_ms": result.end_to_end_latency_ms,
                "fallback_chain": result.decision.fallback_chain,
                "fallback_trace": result.fallback_trace,
                "reason": result.decision.reason,
                "guardrails": result.guardrail_result.model_dump(mode="json"),
                "provider": "ollama" if selected_model.startswith("ollama/") else "openrouter",
                "transparency_note": _build_transparency_note(
                    selected_model=selected_model,
                    requested_model=request.preferred_model,
                    decision_reason=result.decision.reason,
                    guardrail=result.guardrail_result.model_dump(mode="json"),
                ),
            }

        decision = RouterEngine().decide(routing_request, models)
        selected_model = decision.selected_model
        guardrail = {
            "passed": True,
            "injection_detected": False,
            "pii_detected": False,
            "risk_score": 0.0,
            "reason": None,
            "reason_codes": [],
        }
        return {
            "selected_model": selected_model,
            "task_type": decision.task_type.value,
            "budget_priority": request.budget_priority.value,
            "requested_model": request.preferred_model,
            "requested_model_applied": bool(
                request.preferred_model and request.preferred_model == selected_model
            ),
            "response_text": "",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "end_to_end_latency_ms": 0.0,
            "fallback_chain": decision.fallback_chain,
            "fallback_trace": [],
            "reason": decision.reason,
            "guardrails": guardrail,
            "provider": "ollama" if selected_model.startswith("ollama/") else "openrouter",
            "transparency_note": _build_transparency_note(
                selected_model=selected_model,
                requested_model=request.preferred_model,
                decision_reason=decision.reason,
                guardrail=guardrail,
            ),
        }


class DemoRequestRouter:
    """Pure request router for demo HTTP endpoints."""

    def __init__(
        self,
        services: dict[str, DemoBackendService] | None = None,
        live_service: LiveBackendService | None = None,
    ) -> None:
        self._services = services if services is not None else dict(_SERVICES)
        self._live_service = live_service if live_service is not None else LiveBackendService()

    def _service_for(self, query: dict) -> DemoBackendService:
        """Return the service instance matching the ?mode= query param."""
        mode = query.get("mode", ["standard"])[0]
        return self._services.get(mode, self._services["standard"])

    def handle_request(
        self,
        method: str,
        path: str,
        body: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """Handle an HTTP request and return status code plus JSON payload."""
        parsed = urlparse(path)
        route = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        if method == "GET" and route == "/demo/scenarios":
            return 200, asyncio.run(self._service_for(query).list_scenarios_endpoint())

        if method == "GET" and route == "/demo/summary":
            return 200, asyncio.run(self._service_for(query).executive_summary_endpoint())

        if method == "GET" and route == "/demo/safety-feed":
            limit = _parse_int(query.get("limit", ["10"])[0], default=10)
            return 200, asyncio.run(self._service_for(query).safety_feed_endpoint(limit=limit))

        if method == "GET" and route == "/demo/compare":
            scenario_id = query.get("scenario_id", [""])[0]
            if not scenario_id:
                return 400, {"error": "missing_scenario_id"}
            payload = asyncio.run(self._service_for(query).compare_endpoint(scenario_id))
            return (404 if payload.get("error") == "scenario_not_found" else 200), payload

        if method == "POST" and route == "/demo/route-execute":
            if body is None:
                return 400, {"error": "missing_body"}
            try:
                request_json = json.loads(body)
            except json.JSONDecodeError:
                return 400, {"error": "invalid_json"}
            try:
                request = DemoRouteRequest.model_validate(request_json)
            except Exception as exc:
                return 400, {"error": "invalid_request", "reason": str(exc)}

            payload = asyncio.run(self._service_for(query).route_execute_endpoint(request))
            return (404 if payload.get("error") == "scenario_not_found" else 200), payload

        if method == "GET" and route == "/live/models":
            payload = asyncio.run(self._live_service.list_models_endpoint())
            return (503 if payload.get("error") == "live_mode_unavailable" else 200), payload

        if method == "GET" and route == "/live/stats":
            return 200, asyncio.run(self._live_service.stats_endpoint())

        if method == "POST" and route == "/live/route-execute":
            if body is None:
                return 400, {"error": "missing_body"}
            try:
                request_json = json.loads(body)
            except json.JSONDecodeError:
                return 400, {"error": "invalid_json"}

            try:
                request = LiveRouteRequest.model_validate(request_json)
            except Exception as exc:
                return 400, {"error": "invalid_request", "reason": str(exc)}

            payload = asyncio.run(self._live_service.route_execute_endpoint(request))
            status = 503 if payload.get("error") == "live_mode_unavailable" else 200
            return status, payload

        return 404, {"error": "not_found", "path": route, "method": method}


def create_handler(router: DemoRequestRouter) -> type[BaseHTTPRequestHandler]:
    """Create a request handler bound to a router instance."""

    class DemoHTTPRequestHandler(BaseHTTPRequestHandler):
        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._send_cors_headers()
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            route = parsed.path.rstrip("/") or "/"
            if route in {"/", "/index.html"}:
                self._send_html(200, _load_demo_ui_html())
                return

            status, payload = router.handle_request("GET", self.path)
            self._send_json(status, payload)

        def do_POST(self) -> None:  # noqa: N802
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""
            status, payload = router.handle_request("POST", self.path, body)
            self._send_json(status, payload)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            response = json.dumps(payload).encode("utf-8")
            self._write_response(
                status=status,
                content_type="application/json",
                response=response,
            )

        def _send_html(self, status: int, payload: str) -> None:
            response = payload.encode("utf-8")
            self._write_response(
                status=status,
                content_type="text/html; charset=utf-8",
                response=response,
            )

        def _write_response(self, status: int, content_type: str, response: bytes) -> None:
            try:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(response)))
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(response)
            except (BrokenPipeError, ConnectionResetError):
                return

        def _send_cors_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

    return DemoHTTPRequestHandler


def serve_demo_api(host: str = "127.0.0.1", port: int = 8085) -> None:
    """Run the EAR demo API server until interrupted."""
    router = DemoRequestRouter()
    handler = create_handler(router)
    with ThreadingHTTPServer((host, port), handler) as server:
        server.serve_forever()


def _parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_demo_ui_html() -> str:
    """Return the demo UI HTML served at the root path."""
    return _DEMO_HTML_PATH.read_text(encoding="utf-8")


def _build_transparency_note(
    selected_model: str,
    requested_model: str | None,
    decision_reason: str,
    guardrail: dict[str, Any],
) -> str:
    if selected_model.startswith("ollama/") and not guardrail.get("passed", True):
        return (
            "Guardrails blocked cloud routing and EAR shifted execution to Ollama "
            "for local-only inference."
        )

    if selected_model.startswith("ollama/") and guardrail.get("pii_detected", False):
        return (
            "PII safeguards prioritized a trusted local model, so EAR routed to Ollama."
        )

    if requested_model and requested_model != selected_model:
        return (
            f"You requested '{requested_model}', but EAR selected '{selected_model}' "
            f"based on routing policy: {decision_reason}"
        )

    if requested_model and requested_model == selected_model:
        return "Requested model was selected and still validated by EAR routing policy."

    return f"EAR selected '{selected_model}' using task, budget, safety, and fallback scoring."
