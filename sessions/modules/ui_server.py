"""Simple HTTP server for iPhone 5s browser UI."""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

from system.logger import get_logger

LOGGER = get_logger("ui_server")

# Import UI state from basic_commands module
try:
    from sessions.modules.basic_commands import _ui_state, _ui_lock
except ImportError:
    # Fallback if module not loaded
    _ui_state: Dict[str, Any] = {"face_mode": "normal", "last_update": time.time()}
    _ui_lock = threading.Lock()


class UIRequestHandler(BaseHTTPRequestHandler):
    """Simple request handler for iPhone UI."""
    
    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == "/" or self.path == "/index.html":
            self._serve_html()
        elif self.path == "/api/state":
            self._serve_state()
        else:
            self.send_error(404)
    
    def _serve_html(self) -> None:
        """Serve the HTML page for iPhone 5s."""
        html = """<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Tokymon Face</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            background: #000;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            font-family: Arial, sans-serif;
        }
        .face-container {
            width: 200px;
            height: 200px;
            position: relative;
        }
        .eye {
            width: 30px;
            height: 30px;
            background: #fff;
            border-radius: 50%;
            position: absolute;
            top: 60px;
        }
        .eye.left { left: 50px; }
        .eye.right { right: 50px; }
        .pupil {
            width: 12px;
            height: 12px;
            background: #000;
            border-radius: 50%;
            position: absolute;
            top: 9px;
            left: 9px;
            transition: all 0.3s;
        }
        .nose {
            width: 8px;
            height: 20px;
            background: #fff;
            position: absolute;
            top: 100px;
            left: 96px;
        }
        .mouth {
            width: 60px;
            height: 20px;
            border: 3px solid #fff;
            border-top: none;
            border-radius: 0 0 60px 60px;
            position: absolute;
            top: 140px;
            left: 70px;
        }
        .blink {
            height: 2px;
            transition: height 0.1s;
        }
    </style>
</head>
<body>
    <div class="face-container">
        <div class="eye left">
            <div class="pupil" id="pupil-l"></div>
        </div>
        <div class="eye right">
            <div class="pupil" id="pupil-r"></div>
        </div>
        <div class="nose"></div>
        <div class="mouth" id="mouth"></div>
    </div>
    <script>
        function updateFace(mode) {
            const mouth = document.getElementById('mouth');
            const pupils = [document.getElementById('pupil-l'), document.getElementById('pupil-r')];
            
            // Mouth animation based on mode
            if (mode === 'speaking' || mode === 'moving') {
                mouth.style.height = '25px';
            } else {
                mouth.style.height = '20px';
            }
            
            // Pupil position (center for all modes)
            pupils.forEach(p => {
                p.style.top = '9px';
                p.style.left = '9px';
            });
        }
        
        // Poll for state updates
        function pollState() {
            fetch('/api/state')
                .then(r => r.json())
                .then(data => {
                    updateFace(data.face_mode);
                })
                .catch(e => console.error('Poll error:', e));
        }
        
        // Poll every 200ms
        setInterval(pollState, 200);
        pollState();
        
        // Blink animation
        setInterval(() => {
            const eyes = document.querySelectorAll('.eye');
            eyes.forEach(eye => {
                eye.classList.add('blink');
                setTimeout(() => eye.classList.remove('blink'), 100);
            });
        }, 2000);
    </script>
</body>
</html>"""
        
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())
    
    def _serve_state(self) -> None:
        """Serve current UI state as JSON."""
        with _ui_lock:
            state = _ui_state.copy()
        
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(state).encode())
    
    def log_message(self, format: str, *args: object) -> None:
        """Suppress default logging."""
        pass


_ui_server: Optional[HTTPServer] = None
_ui_server_thread: Optional[threading.Thread] = None


def start_ui_server(port: int = 8080) -> None:
    """Start the iPhone UI HTTP server."""
    global _ui_server, _ui_server_thread
    
    if _ui_server is not None:
        return  # Already running
    
    def run_server() -> None:
        global _ui_server
        try:
            _ui_server = HTTPServer(("0.0.0.0", port), UIRequestHandler)
            LOGGER.info("iPhone UI server started on port %d", port)
            _ui_server.serve_forever()
        except Exception as exc:
            LOGGER.error("UI server error: %s", exc)
    
    _ui_server_thread = threading.Thread(target=run_server, daemon=True)
    _ui_server_thread.start()


def stop_ui_server() -> None:
    """Stop the iPhone UI HTTP server."""
    global _ui_server
    if _ui_server:
        _ui_server.shutdown()
        _ui_server = None
        LOGGER.info("iPhone UI server stopped")

