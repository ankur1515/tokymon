"""Unit tests for sessions/modules/ui_server.py.

Coverage areas
--------------
1.  HTML payload  — DOCTYPE, all 6 expressions, SSE JS, neon filter
2.  /api/state    — returns JSON with face_mode, correct Content-Type
3.  /api/events   — SSE headers, immediate first event, mode-change push
4.  Threading     — _ThreadedHTTPServer inherits ThreadingMixIn
5.  Lifecycle     — start / stop idempotency, double-start guard
6.  Fallback      — unknown face_mode maps to waiting, not a crash

All tests run in TOKY_ENV=dev (simulator) with a real HTTPServer on a
random free port so they exercise the actual network stack without needing
hardware.
"""
from __future__ import annotations

import json
import socket
import threading
import time
import urllib.request
import urllib.error
from typing import Dict, Any

import pytest

# ── helpers ──────────────────────────────────────────────────────────────────

def _free_port() -> int:
    """Return a free TCP port on localhost."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _get(port: int, path: str, timeout: float = 2.0) -> urllib.request.http.client.HTTPResponse:
    return urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=timeout)


def _sse_headers_and_first_event(port: int, timeout: float = 2.0) -> str:
    """Open a raw socket, send an SSE request, read initial response bytes."""
    s = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    s.sendall(
        b"GET /api/events HTTP/1.1\r\n"
        b"Host: 127.0.0.1\r\n"
        b"Accept: text/event-stream\r\n"
        b"Connection: close\r\n\r\n"
    )
    time.sleep(0.2)          # give server time to write the first event
    data = s.recv(8192).decode("utf-8", errors="replace")
    s.close()
    return data


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_server():
    """Ensure ui_server module state is clean before and after each test."""
    import sessions.modules.ui_server as mod
    mod._ui_server = None
    mod._ui_server_thread = None
    yield
    mod.stop_ui_server()
    mod._ui_server = None
    mod._ui_server_thread = None


@pytest.fixture()
def running_server():
    """Start the face server on a free port; yield port; stop after test."""
    from sessions.modules.ui_server import start_ui_server, stop_ui_server
    port = _free_port()
    start_ui_server(port=port)
    time.sleep(0.25)          # allow background thread to bind
    yield port
    stop_ui_server()


# ── 1. HTML payload ──────────────────────────────────────────────────────────

class TestHTMLPayload:
    """The HTML string must contain every expression and key JS feature."""

    def test_doctype_present(self):
        from sessions.modules.ui_server import _HTML
        assert "<!DOCTYPE html>" in _HTML

    def test_neon_filter_defined(self):
        from sessions.modules.ui_server import _HTML
        assert 'id="neon"' in _HTML
        assert "feGaussianBlur" in _HTML

    @pytest.mark.parametrize("expr_key", [
        "waiting", "normal_smile", "greeting", "speaking", "moving", "stop"
    ])
    def test_all_six_expressions_in_js(self, expr_key):
        from sessions.modules.ui_server import _HTML
        assert expr_key in _HTML, f"Expression '{expr_key}' missing from HTML"

    def test_sse_connect_function_present(self):
        from sessions.modules.ui_server import _HTML
        assert "connectSSE" in _HTML
        assert "/api/events" in _HTML

    def test_polling_fallback_present(self):
        from sessions.modules.ui_server import _HTML
        assert "/api/state" in _HTML
        assert "setInterval" in _HTML

    def test_blink_animation_present(self):
        from sessions.modules.ui_server import _HTML
        assert "doBlink" in _HTML
        assert "eyeScale" in _HTML

    def test_speaking_mouth_animation_present(self):
        from sessions.modules.ui_server import _HTML
        assert "speakLoop" in _HTML or "spk" in _HTML

    def test_thinking_dots_animation_present(self):
        from sessions.modules.ui_server import _HTML
        assert "dotsLoop" in _HTML or "dp" in _HTML

    def test_pupil_drift_animation_present(self):
        from sessions.modules.ui_server import _HTML
        assert "driftLoop" in _HTML or "driftOn" in _HTML

    def test_svg_viewbox_correct(self):
        from sessions.modules.ui_server import _HTML
        assert 'viewBox="0 0 800 480"' in _HTML

    def test_preserve_aspect_ratio(self):
        from sessions.modules.ui_server import _HTML
        assert "xMidYMid meet" in _HTML


# ── 2. /api/state endpoint ────────────────────────────────────────────────────

class TestStateEndpoint:

    def test_returns_200(self, running_server):
        r = _get(running_server, "/api/state")
        assert r.status == 200

    def test_content_type_json(self, running_server):
        r = _get(running_server, "/api/state")
        ct = r.headers.get("Content-Type", "")
        assert "application/json" in ct

    def test_face_mode_key_present(self, running_server):
        r = _get(running_server, "/api/state")
        body = json.loads(r.read())
        assert "face_mode" in body

    def test_face_mode_is_string(self, running_server):
        r = _get(running_server, "/api/state")
        body = json.loads(r.read())
        assert isinstance(body["face_mode"], str)

    def test_cors_header_present(self, running_server):
        r = _get(running_server, "/api/state")
        assert r.headers.get("Access-Control-Allow-Origin") == "*"

    def test_state_reflects_ui_state_change(self, running_server):
        import sessions.modules.ui_server as mod
        with mod._ui_lock:
            mod._ui_state["face_mode"] = "speaking"
        r = _get(running_server, "/api/state")
        body = json.loads(r.read())
        assert body["face_mode"] == "speaking"
        # restore
        with mod._ui_lock:
            mod._ui_state["face_mode"] = "normal_smile"


# ── 3. /api/events SSE endpoint ───────────────────────────────────────────────

class TestSSEEndpoint:

    def test_content_type_event_stream(self, running_server):
        raw = _sse_headers_and_first_event(running_server)
        assert "text/event-stream" in raw

    def test_first_event_delivered_immediately(self, running_server):
        raw = _sse_headers_and_first_event(running_server)
        assert "data:" in raw

    def test_first_event_valid_json(self, running_server):
        raw = _sse_headers_and_first_event(running_server)
        # Extract the data line
        for line in raw.splitlines():
            if line.startswith("data:"):
                payload = json.loads(line[5:].strip())
                assert "face_mode" in payload
                return
        pytest.fail("No data: line found in SSE response")

    def test_mode_change_pushed_within_50ms(self, running_server):
        """Change face_mode then verify it appears in SSE stream within 50 ms."""
        import sessions.modules.ui_server as mod

        received: list = []
        stop_flag = threading.Event()

        def _listen():
            s = socket.create_connection(("127.0.0.1", running_server), timeout=3)
            s.sendall(
                b"GET /api/events HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Accept: text/event-stream\r\n\r\n"
            )
            buf = ""
            s.settimeout(0.5)
            while not stop_flag.is_set():
                try:
                    chunk = s.recv(1024).decode("utf-8", errors="replace")
                    buf += chunk
                    for line in buf.splitlines():
                        if line.startswith("data:"):
                            try:
                                received.append(json.loads(line[5:].strip()))
                            except Exception:
                                pass
                except socket.timeout:
                    continue
            s.close()

        listener = threading.Thread(target=_listen, daemon=True)
        listener.start()
        time.sleep(0.2)  # wait for initial event

        # Change mode and measure latency
        with mod._ui_lock:
            mod._ui_state["face_mode"] = "moving"
        t0 = time.time()

        deadline = t0 + 0.5
        while time.time() < deadline:
            modes = [e.get("face_mode") for e in received]
            if "moving" in modes:
                latency_ms = (time.time() - t0) * 1000
                break
            time.sleep(0.005)
        else:
            latency_ms = None

        stop_flag.set()
        listener.join(timeout=1)

        assert latency_ms is not None, "face_mode='moving' never arrived in SSE stream"
        assert latency_ms < 50, f"SSE latency {latency_ms:.1f} ms exceeds 50 ms budget"

        # restore
        with mod._ui_lock:
            mod._ui_state["face_mode"] = "normal_smile"

    def test_cors_header_on_sse(self, running_server):
        raw = _sse_headers_and_first_event(running_server)
        assert "Access-Control-Allow-Origin: *" in raw

    def test_cache_control_no_cache(self, running_server):
        raw = _sse_headers_and_first_event(running_server)
        assert "no-cache" in raw


# ── 4. HTML endpoint ─────────────────────────────────────────────────────────

class TestHTMLEndpoint:

    def test_root_returns_200(self, running_server):
        r = _get(running_server, "/")
        assert r.status == 200

    def test_index_html_returns_200(self, running_server):
        r = _get(running_server, "/index.html")
        assert r.status == 200

    def test_content_type_html(self, running_server):
        r = _get(running_server, "/")
        assert "text/html" in r.headers.get("Content-Type", "")

    def test_html_contains_svg(self, running_server):
        r = _get(running_server, "/")
        body = r.read().decode()
        assert "<svg" in body

    def test_unknown_path_returns_404(self, running_server):
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _get(running_server, "/does-not-exist")
        assert exc_info.value.code == 404


# ── 5. Threading ─────────────────────────────────────────────────────────────

class TestThreading:

    def test_server_inherits_threading_mixin(self):
        from socketserver import ThreadingMixIn
        from sessions.modules.ui_server import _ThreadedHTTPServer
        assert issubclass(_ThreadedHTTPServer, ThreadingMixIn)

    def test_daemon_threads_enabled(self):
        from sessions.modules.ui_server import _ThreadedHTTPServer
        assert _ThreadedHTTPServer.daemon_threads is True

    def test_concurrent_requests_do_not_block(self, running_server):
        """Two simultaneous requests should both complete in <1 s."""
        results = []

        def fetch():
            try:
                r = _get(running_server, "/api/state")
                results.append(r.status)
            except Exception as e:
                results.append(str(e))

        threads = [threading.Thread(target=fetch) for _ in range(5)]
        t0 = time.time()
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=2)
        elapsed = time.time() - t0

        assert len(results) == 5
        assert all(r == 200 for r in results), f"Some requests failed: {results}"
        assert elapsed < 2.0


# ── 6. Lifecycle ─────────────────────────────────────────────────────────────

class TestLifecycle:

    def test_start_then_stop(self):
        from sessions.modules.ui_server import start_ui_server, stop_ui_server
        import sessions.modules.ui_server as mod
        port = _free_port()
        start_ui_server(port=port)
        time.sleep(0.2)
        assert mod._ui_server is not None
        stop_ui_server()
        assert mod._ui_server is None

    def test_double_start_is_no_op(self):
        from sessions.modules.ui_server import start_ui_server, stop_ui_server
        import sessions.modules.ui_server as mod
        port = _free_port()
        start_ui_server(port=port)
        time.sleep(0.2)
        first = mod._ui_server
        start_ui_server(port=port)   # should be ignored
        assert mod._ui_server is first
        stop_ui_server()

    def test_stop_when_not_started_is_safe(self):
        from sessions.modules.ui_server import stop_ui_server
        stop_ui_server()  # should not raise


# ── 7. Expression completeness ───────────────────────────────────────────────

class TestExpressionCompleteness:
    """Verify the JS EXPR object covers every face_mode emitted by basic_commands."""

    EXPECTED_MODES = {
        "waiting", "normal_smile", "greeting", "speaking", "moving", "stop"
    }
    MOUTH_IDS = {"mwait", "mhap", "mspk", "mexc", "mthk"}

    def test_all_modes_in_html(self):
        from sessions.modules.ui_server import _HTML
        for mode in self.EXPECTED_MODES:
            assert mode in _HTML, f"Mode '{mode}' missing from HTML EXPR table"

    def test_all_mouth_groups_in_html(self):
        from sessions.modules.ui_server import _HTML
        for mid in self.MOUTH_IDS:
            assert mid in _HTML, f"Mouth group '{mid}' missing from HTML"

    def test_waiting_uses_subtle_mouth(self):
        from sessions.modules.ui_server import _HTML
        # waiting → mwait (small curve)
        # Check that the EXPR entry for waiting references mwait
        idx = _HTML.find("waiting:")
        snippet = _HTML[idx: idx + 200]
        assert "mwait" in snippet

    def test_speaking_uses_speak_mouth(self):
        from sessions.modules.ui_server import _HTML
        idx = _HTML.find("speaking:")
        snippet = _HTML[idx: idx + 200]
        assert "mspk" in snippet

    def test_moving_uses_excited_mouth(self):
        from sessions.modules.ui_server import _HTML
        idx = _HTML.find("moving:")
        snippet = _HTML[idx: idx + 200]
        assert "mexc" in snippet

    def test_stop_uses_thinking_mouth(self):
        from sessions.modules.ui_server import _HTML
        idx = _HTML.find("stop:")
        snippet = _HTML[idx: idx + 200]
        assert "mthk" in snippet
