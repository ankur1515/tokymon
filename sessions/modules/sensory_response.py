"""Sensory Response Observation module."""
from __future__ import annotations

from sessions.modules.base import BaseModule, ModuleResult


class SensoryResponseModule(BaseModule):
    """Module 8: Sensory Response Observation - Thin adapter."""

    def __init__(self) -> None:
        super().__init__("sensory_response")

    def enter(self) -> None:
        """Initialize sensory response observation."""
        self.logger.info("Module start: sensory_response")

    def run(self) -> ModuleResult:
        """Run sensory response observation - thin adapter."""
        self._set_running(True)
        if self._stop_requested:
            self._set_running(False)
            return ModuleResult(completed=False, engagement=None)
        self._set_running(False)
        return ModuleResult(completed=True, engagement=None)

    def exit(self) -> None:
        """Cleanup sensory response observation."""
        self.logger.info("Module end: sensory_response")
