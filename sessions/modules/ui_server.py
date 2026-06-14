"""Tokymon 5.2-inch touchscreen face server.

Serves a neon SVG face designed for autistic children via a threaded HTTP
server.  Server-Sent Events (SSE) replace the original 200 ms client poll so
expression changes reach the display in under 15 ms.

Expression → face_mode mapping (set by basic_commands.py, unchanged):
    waiting      → calm neutral, slow pupil drift, auto-blink  (boot / idle)
    normal_smile → happy open face, wide warm smile, auto-blink
    greeting     → same as normal_smile
    speaking     → open eyes, animated pulsing mouth
    moving       → excited squint eyes, very wide smile
    stop         → thinking face, pupils up, pulsing dots

Public API is unchanged: start_ui_server(port), stop_ui_server()
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any, Dict, Optional

from system.logger import get_logger

LOGGER = get_logger("ui_server")

try:
    from sessions.modules.basic_commands import _ui_state, _ui_lock
except ImportError:
    _ui_state: Dict[str, Any] = {"face_mode": "waiting", "last_update": time.time()}
    _ui_lock = threading.Lock()


class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Each connection (including long-lived SSE streams) gets its own thread."""
    daemon_threads = True


# ---------------------------------------------------------------------------
# Face HTML — single module-level constant, built once at import time.
# Designed for 800×480 (standard 5-inch Pi touchscreen).
# viewBox="0 0 800 480" + preserveAspectRatio scales to any resolution.
# ---------------------------------------------------------------------------
_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=800,height=480,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Tokymon</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:100%;background:#000;overflow:hidden;display:flex;align-items:center;justify-content:center}
svg{display:block;width:100vw;height:100vh}
</style>
</head>
<body>
<svg id="face" viewBox="0 0 800 480" preserveAspectRatio="xMidYMid meet"
     xmlns="http://www.w3.org/2000/svg">
<defs>
  <!--
    Three-layer neon glow: tight highlight (2px) + medium halo (7px) +
    outer bloom (18px) merged back with the original crisp stroke.
    Applied once to the root group so every element shares the same look.
  -->
  <filter id="neon" x="-50%" y="-50%" width="200%" height="200%">
    <feGaussianBlur stdDeviation="2"  result="a"/>
    <feGaussianBlur stdDeviation="7"  result="b"/>
    <feGaussianBlur stdDeviation="18" result="c"/>
    <feMerge>
      <feMergeNode in="c"/>
      <feMergeNode in="b"/>
      <feMergeNode in="a"/>
      <feMergeNode in="SourceGraphic"/>
    </feMerge>
  </filter>
</defs>

<!-- Root group: neon filter + shared stroke style -->
<g filter="url(#neon)" stroke="#5ce0f5" fill="none" stroke-linecap="round">

  <!-- ── EYEBROWS ──────────────────────────────────────────────────────── -->
  <!-- Paths swapped by JS on each expression change -->
  <path id="lb" stroke-width="7" d="M 112 92 Q 195 76 278 88"/>
  <path id="rb" stroke-width="7" d="M 522 88 Q 605 76 688 92"/>

  <!-- ── LEFT EYE RING ─────────────────────────────────────────────────── -->
  <!-- Wrapped in a <g> so scaleY(0) collapses it for the blink animation.
       transform-origin must match the eye centre in SVG coordinates.       -->
  <g id="lew" style="transform-origin:195px 200px">
    <circle cx="195" cy="200" r="88" stroke-width="11"/>
  </g>

  <!-- ── RIGHT EYE RING ────────────────────────────────────────────────── -->
  <g id="rew" style="transform-origin:605px 200px">
    <circle cx="605" cy="200" r="88" stroke-width="11"/>
  </g>

  <!-- ── LEFT PUPIL ────────────────────────────────────────────────────── -->
  <!-- Also wrapped for blink scaleY so pupil disappears with the eye ring. -->
  <g id="lpw" style="transform-origin:195px 200px">
    <circle id="lp" cx="216" cy="176" r="14" fill="#fff" stroke="none"/>
  </g>

  <!-- ── RIGHT PUPIL ───────────────────────────────────────────────────── -->
  <g id="rpw" style="transform-origin:605px 200px">
    <circle id="rp" cx="626" cy="176" r="14" fill="#fff" stroke="none"/>
  </g>

  <!-- ── EXCITED EYE ARCS (squinted joy ^^ shape, moving only) ─────────── -->
  <g id="xe" opacity="0">
    <path d="M 107 200 Q 195 110 283 200" stroke-width="11"/>
    <path d="M 517 200 Q 605 110 693 200" stroke-width="11"/>
    <!-- inner depth lines give the squint more volume -->
    <path d="M 126 192 Q 195 136 264 192" stroke-width="5" opacity="0.4"/>
    <path d="M 536 192 Q 605 136 674 192" stroke-width="5" opacity="0.4"/>
  </g>

  <!-- ── MOUTHS ─────────────────────────────────────────────────────────── -->
  <!-- One per expression; only one is visible at a time.                   -->

  <!-- waiting: tiny subtle curve — calm, non-threatening resting state -->
  <g id="mwait">
    <path d="M 344 396 Q 400 412 456 396" stroke-width="8"/>
  </g>

  <!-- normal_smile / greeting: wide warm smile -->
  <g id="mhap" opacity="0">
    <path d="M 272 385 Q 400 436 528 385" stroke-width="9"/>
  </g>

  <!-- speaking: animated ellipse — JS drives ry between 10 and 42 -->
  <g id="mspk" opacity="0">
    <ellipse id="se" cx="400" cy="400" rx="56" ry="14" stroke-width="9"/>
  </g>

  <!-- moving / excited: very wide open smile + faint inner echo -->
  <g id="mexc" opacity="0">
    <path d="M 248 380 Q 400 444 552 380" stroke-width="9"/>
    <path d="M 270 382 Q 400 426 530 382" stroke-width="5" opacity="0.35"/>
  </g>

  <!-- stop / thinking: small calm closed curve -->
  <g id="mthk" opacity="0">
    <path d="M 348 394 Q 400 408 452 394" stroke-width="8"/>
  </g>

  <!-- ── THINKING DOTS (pulsing, shown only for stop/thinking) ──────────── -->
  <g id="tdots" opacity="0" fill="#5ce0f5" stroke="none">
    <circle id="d1" cx="362" cy="52" r="7"/>
    <circle id="d2" cx="400" cy="38" r="7"/>
    <circle id="d3" cx="438" cy="52" r="7"/>
  </g>

</g><!-- end neon group -->
</svg>

<script>
// ── Expression definitions ─────────────────────────────────────────────────
// Each entry describes every visual change needed for that face_mode.
//   lb/rb   : SVG path data for left/right eyebrow
//   rings   : show normal circular eye rings
//   pupils  : show pupils
//   drift   : enable slow idle pupil drift (waiting only)
//   mouth   : which mouth group id to show
//   exc     : show excited squint arcs instead of rings
//   dots    : show thinking dots
//   blink   : enable random auto-blink
//   lpx/lpy : default pupil position (left), rpx/rpy (right)
var EXPR = {
  waiting: {
    lb:"M 112 92 Q 195 76 278 88", rb:"M 522 88 Q 605 76 688 92",
    rings:1,pupils:1,drift:1,mouth:"mwait",exc:0,dots:0,blink:1,
    lpx:216,lpy:176,rpx:626,rpy:176
  },
  normal_smile: {
    lb:"M 108 82 Q 195 64 280 78", rb:"M 520 78 Q 605 64 692 82",
    rings:1,pupils:1,drift:0,mouth:"mhap",exc:0,dots:0,blink:1,
    lpx:216,lpy:176,rpx:626,rpy:176
  },
  greeting: {
    lb:"M 108 82 Q 195 64 280 78", rb:"M 520 78 Q 605 64 692 82",
    rings:1,pupils:1,drift:0,mouth:"mhap",exc:0,dots:0,blink:1,
    lpx:216,lpy:176,rpx:626,rpy:176
  },
  speaking: {
    lb:"M 108 82 Q 195 64 280 78", rb:"M 520 78 Q 605 64 692 82",
    rings:1,pupils:1,drift:0,mouth:"mspk",exc:0,dots:0,blink:0,
    lpx:216,lpy:176,rpx:626,rpy:176
  },
  moving: {
    lb:"M 104 64 Q 195 42 284 60", rb:"M 516 60 Q 605 42 696 64",
    rings:0,pupils:0,drift:0,mouth:"mexc",exc:1,dots:0,blink:0,
    lpx:216,lpy:176,rpx:626,rpy:176
  },
  stop: {
    lb:"M 112 90 Q 195 76 278 86", rb:"M 520 68 Q 605 46 692 68",
    rings:1,pupils:1,drift:0,mouth:"mthk",exc:1,dots:1,blink:0,
    lpx:210,lpy:158,rpx:620,rpy:158
  }
};

var MOUTHS = ["mwait","mhap","mspk","mexc","mthk"];
var cur = null, spk = false, blinkOn = false, driftOn = false;

// DOM refs — grabbed once at startup
var lew   = document.getElementById('lew');
var rew   = document.getElementById('rew');
var lpw   = document.getElementById('lpw');
var rpw   = document.getElementById('rpw');
var lp    = document.getElementById('lp');
var rp    = document.getElementById('rp');
var lb    = document.getElementById('lb');
var rb    = document.getElementById('rb');
var xe    = document.getElementById('xe');
var se    = document.getElementById('se');
var tdots = document.getElementById('tdots');
var d1    = document.getElementById('d1');
var d2    = document.getElementById('d2');
var d3    = document.getElementById('d3');

function setOp(id, v) {
  var el = document.getElementById(id);
  if (el) el.style.opacity = v ? '1' : '0';
}

function eyeScale(v) {
  var t = 'scaleY(' + v + ')';
  lew.style.transform = t;
  rew.style.transform = t;
  lpw.style.transform = t;
  rpw.style.transform = t;
}

// ── Apply a named expression ───────────────────────────────────────────────
function apply(name) {
  var e = EXPR[name] || EXPR['waiting'];
  if (cur === name) return;   // already in this state — no-op
  cur = name;

  // eyebrows
  lb.setAttribute('d', e.lb);
  rb.setAttribute('d', e.rb);

  // eye rings and pupils
  lew.style.opacity = e.rings ? '1' : '0';
  rew.style.opacity = e.rings ? '1' : '0';
  lpw.style.opacity = e.pupils ? '1' : '0';
  rpw.style.opacity = e.pupils ? '1' : '0';

  // pupil default position (drift/thinking override this at runtime)
  if (e.pupils) {
    lp.setAttribute('cx', e.lpx);
    lp.setAttribute('cy', e.lpy);
    rp.setAttribute('cx', e.rpx);
    rp.setAttribute('cy', e.rpy);
  }

  // excited squint arcs
  xe.style.opacity = e.exc ? '1' : '0';

  // mouth — show exactly one
  MOUTHS.forEach(function(m) { setOp(m, m === e.mouth); });

  // thinking dots
  tdots.style.opacity = e.dots ? '1' : '0';

  // animation flags for the continuous loops below
  blinkOn = !!e.blink;
  driftOn = !!e.drift;
  spk     = (name === 'speaking');

  // reset eye scale if blink is disabled (guards against mid-blink switch)
  if (!blinkOn) eyeScale(1);
}

// ── Speaking mouth pulse ───────────────────────────────────────────────────
// Runs every rAF; only moves ry when spk === true.
var st = 0;
(function speakLoop() {
  if (spk) {
    st += 0.13;
    se.setAttribute('ry', Math.round(10 + Math.abs(Math.sin(st)) * 32));
  }
  requestAnimationFrame(speakLoop);
})();

// ── Thinking dots pulse ────────────────────────────────────────────────────
var dp = 0;
(function dotsLoop() {
  dp += 0.055;
  [d1, d2, d3].forEach(function(d, i) {
    if (d) d.setAttribute('opacity', Math.max(0.08, Math.sin(dp - i * 1.1)).toFixed(2));
  });
  requestAnimationFrame(dotsLoop);
})();

// ── Idle pupil drift (waiting mode only) ──────────────────────────────────
// Pupils slowly wander in a Lissajous-like path so the face feels alive.
var pt = 0;
(function driftLoop() {
  if (driftOn && cur && EXPR[cur]) {
    pt += 0.007;
    var e = EXPR[cur];
    lp.setAttribute('cx', (e.lpx + Math.sin(pt)       * 7).toFixed(1));
    lp.setAttribute('cy', (e.lpy + Math.sin(pt * 0.6) * 4).toFixed(1));
    rp.setAttribute('cx', (e.rpx + Math.sin(pt)       * 7).toFixed(1));
    rp.setAttribute('cy', (e.rpy + Math.sin(pt * 0.6) * 4).toFixed(1));
  }
  requestAnimationFrame(driftLoop);
})();

// ── Blink animation ────────────────────────────────────────────────────────
// Uses scaleY on the eye wrapper groups so the ring + pupil both collapse.
// Close: 6 steps × 16 ms = 96 ms.  Hold: 55 ms.  Open: 6 steps × 18 ms.
function doBlink() {
  if (!blinkOn) { scheduleBlink(); return; }
  var step = 0, N = 6;

  function closeEye() {
    step++;
    eyeScale(Math.max(0, 1 - step / N));
    if (step < N) { setTimeout(closeEye, 16); }
    else           { setTimeout(openEye,  55); }
  }
  function openEye() {
    step--;
    eyeScale(Math.max(0, step / N));
    if (step > 0) { setTimeout(openEye, 18); }
    else          { eyeScale(1); scheduleBlink(); }
  }
  closeEye();
}

function scheduleBlink() {
  setTimeout(doBlink, 2800 + Math.random() * 2400);
}
scheduleBlink();

// ── SSE connection with polling fallback ───────────────────────────────────
// Primary: EventSource at /api/events — server pushes on every state change.
// Fallback: setInterval poll at 200 ms (same as original) if SSE drops.
var lastMode = null;
var pollTimer = null;

function applyMode(mode) {
  if (mode !== lastMode) {
    lastMode = mode;
    apply(mode);
  }
}

function connectSSE() {
  var es = new EventSource('/api/events');
  es.onmessage = function(ev) {
    try { applyMode(JSON.parse(ev.data).face_mode); } catch(e) {}
  };
  es.onerror = function() {
    es.close();
    if (!pollTimer) {
      pollTimer = setInterval(function() {
        fetch('/api/state')
          .then(function(r) { return r.json(); })
          .then(function(d) { applyMode(d.face_mode); })
          .catch(function() {});
      }, 200);
    }
  };
}

try { connectSSE(); } catch(e) { /* SSE not supported — fallback */ }

// Show waiting face immediately (before first SSE event arrives)
apply('waiting');
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# HTTP request handler
# ---------------------------------------------------------------------------

class UIRequestHandler(BaseHTTPRequestHandler):
    """Handles HTML, JSON state, and SSE stream requests."""

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._serve_html()
        elif self.path == "/api/state":
            self._serve_state()
        elif self.path == "/api/events":
            self._serve_sse()
        else:
            self.send_error(404)

    def _serve_html(self) -> None:
        body = _HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_state(self) -> None:
        """JSON snapshot — used as SSE fallback and initial-load check."""
        with _ui_lock:
            state = _ui_state.copy()
        body = json.dumps(state).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_sse(self) -> None:
        """Hold the connection open and push face_mode changes as SSE events.

        Polls _ui_state every 10 ms server-side.  Only writes to the socket
        when the mode actually changes, so there is no bandwidth waste and
        the browser reacts in under 15 ms end-to-end.
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Accel-Buffering", "no")  # disable nginx buffering
        self.end_headers()

        last_mode: Optional[str] = None
        try:
            # Push current state immediately on connect so the face appears
            # at once rather than waiting for the first change.
            with _ui_lock:
                mode = _ui_state.get("face_mode", "waiting")
            self.wfile.write(
                ("data: " + json.dumps({"face_mode": mode}) + "\n\n").encode()
            )
            self.wfile.flush()
            last_mode = mode

            while True:
                with _ui_lock:
                    mode = _ui_state.get("face_mode", "waiting")
                if mode != last_mode:
                    self.wfile.write(
                        ("data: " + json.dumps({"face_mode": mode}) + "\n\n").encode()
                    )
                    self.wfile.flush()
                    last_mode = mode
                time.sleep(0.01)   # 10 ms poll — imperceptible latency

        except (BrokenPipeError, ConnectionResetError, OSError):
            pass  # browser closed the tab / navigated away — normal exit

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # suppress per-request access logs


# ---------------------------------------------------------------------------
# Server lifecycle  (public API unchanged)
# ---------------------------------------------------------------------------

_ui_server: Optional[_ThreadedHTTPServer] = None
_ui_server_thread: Optional[threading.Thread] = None


def start_ui_server(port: int = 8080) -> None:
    """Start the threaded face-display HTTP server (no-op if already running)."""
    global _ui_server, _ui_server_thread

    if _ui_server is not None:
        return

    def _run() -> None:
        global _ui_server
        try:
            _ui_server = _ThreadedHTTPServer(("0.0.0.0", port), UIRequestHandler)
            LOGGER.info("Tokymon face server started on port %d (SSE enabled)", port)
            _ui_server.serve_forever()
        except Exception as exc:
            LOGGER.error("Face server error: %s", exc)

    _ui_server_thread = threading.Thread(target=_run, daemon=True)
    _ui_server_thread.start()


def stop_ui_server() -> None:
    """Gracefully shut down the face-display HTTP server."""
    global _ui_server
    if _ui_server:
        _ui_server.shutdown()
        _ui_server = None
        LOGGER.info("Tokymon face server stopped")
