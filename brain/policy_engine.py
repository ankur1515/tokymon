"""Policy engine to keep the robot safe."""
from __future__ import annotations

from typing import Dict

ALLOWED_DIRECTIONS = {"forward", "backward"}
MAX_DURATION = 2.0


def enforce(intent: Dict) -> Dict:
    action = intent.get("action")
    if action != "move":
        raise ValueError(f"Action {action} not permitted")
    params = intent.get("params", {})
    direction = params.get("dir")
    if direction not in ALLOWED_DIRECTIONS:
        raise ValueError("Direction not allowed")
    duration = float(params.get("duration", 0))
    if not 0 < duration <= MAX_DURATION:
        raise ValueError("Duration out of range")
    return {"action": action, "params": {"dir": direction, "duration": duration}}
