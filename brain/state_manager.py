"""In-memory robot state cache."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class StateManager:
    data: Dict[str, str] = field(default_factory=dict)

    def update(self, key: str, value: str) -> None:
        self.data[key] = value

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.data.get(key, default)
