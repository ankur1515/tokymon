"""Body Movement & Gesture Imitation module."""
from __future__ import annotations

from sessions.modules.base import BaseModule, ModuleResult


class BodyMovementModule(BaseModule):
    """Module 4: Body Movement & Gesture Imitation - Thin adapter."""

    def __init__(self) -> None:
        super().__init__("body_movement")

    def enter(self) -> None:
        """Initialize body movement and gesture imitation."""
        self.logger.info("Module start: body_movement")

    def run(self) -> ModuleResult:
        """Run body movement and gesture imitation - thin adapter."""
        self._set_running(True)
        if self._stop_requested:
            self._set_running(False)
            return ModuleResult(completed=False, engagement=None)
        self._set_running(False)
        return ModuleResult(completed=True, engagement=None)

    def exit(self) -> None:
        """Cleanup body movement and gesture imitation."""
        self.logger.info("Module end: body_movement")
