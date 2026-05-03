"""Local HTTP server for EAR leadership demo endpoints."""
from __future__ import annotations

import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from ear.demo_backend import DemoBackendService, DemoRouteRequest, OLLAMA_REPLAY_SCENARIOS


_DEMO_HTML_PATH = Path(__file__).resolve().parents[2] / "docs" / "llm_explorer.html"

_SERVICES: dict[str, DemoBackendService] = {
    "standard": DemoBackendService(),
    "ollama": DemoBackendService(scenarios=OLLAMA_REPLAY_SCENARIOS),
}


class DemoRequestRouter:
    """Pure request router for demo HTTP endpoints."""

    def __init__(self, services: dict[str, DemoBackendService] | None = None) -> None:
        self._services = services if services is not None else dict(_SERVICES)

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

        return 404, {"error": "not_found", "path": route, "method": method}


def create_handler(router: DemoRequestRouter) -> type[BaseHTTPRequestHandler]:
    """Create a request handler bound to a router instance."""

    class DemoHTTPRequestHandler(BaseHTTPRequestHandler):
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
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(response)

        def _send_html(self, status: int, payload: str) -> None:
            response = payload.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(response)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(response)

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
