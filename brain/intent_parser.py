"""Parse LLM text into structured actions."""
from __future__ import annotations

import json
from typing import Any, Dict

from system.logger import get_logger

LOGGER = get_logger("intent_parser")


SCHEMA = {"action", "params"}


def parse(raw: str) -> Dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        LOGGER.error("Intent parse error: %s", exc)
        raise
    missing = SCHEMA - data.keys()
    if missing:
        raise ValueError(f"Intent missing keys: {missing}")
    if not isinstance(data["params"], dict):
        raise ValueError("params must be dict")
    return data
