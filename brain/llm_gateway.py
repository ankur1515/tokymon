"""LLM gateway stub that routes through intent parser and policy engine."""
from __future__ import annotations

import json

from brain import intent_parser, policy_engine
from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("llm")


def ask_llm(prompt: str, context: dict | None = None) -> dict:
    provider = CONFIG["services"]["llm"]["provider"]
    LOGGER.info("LLM request to %s (stub)", provider)
    # TODO: Implement real provider call; respect CONFIG timeouts and API keys.
    fake_response = json.dumps({
        "action": "move",
        "params": {"dir": "forward", "duration": 1.0},
    })
    intent = intent_parser.parse(fake_response)
    return policy_engine.enforce(intent)
