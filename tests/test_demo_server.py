"""Tests for the local demo HTTP request router."""
from __future__ import annotations

import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from ear.demo_backend import DemoBackendService
import ear.demo_server as demo_server_module
from ear.demo_server import DemoRequestRouter, _parse_int, create_handler, serve_demo_api


class TestParseInt:
    def test_parse_valid(self) -> None:
        assert _parse_int("7", default=1) == 7

    def test_parse_invalid_returns_default(self) -> None:
        assert _parse_int("abc", default=3) == 3

    def test_parse_none_like_returns_default(self) -> None:
        assert _parse_int(None, default=4) == 4  # type: ignore[arg-type]


class TestDemoRequestRouter:
    def setup_method(self) -> None:
        self.router = DemoRequestRouter(DemoBackendService())

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


class TestDemoHttpHandler:
    def test_live_get_and_post_requests(self) -> None:
        router = DemoRequestRouter(DemoBackendService())
        handler = create_handler(router)
        server = demo_server_module.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            base_url = f"http://127.0.0.1:{server.server_port}"

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
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


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
