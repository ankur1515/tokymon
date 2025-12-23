"""Obstacle Course & Motor Planning module."""
from __future__ import annotations

from sessions.modules.base import BaseModule, ModuleResult


class ObstacleCourseModule(BaseModule):
    """Module 6: Obstacle Course & Motor Planning - Thin adapter."""

    def __init__(self) -> None:
        super().__init__("obstacle_course")

    def enter(self) -> None:
        """Initialize obstacle course and motor planning."""
        self.logger.info("Module start: obstacle_course")

    def run(self) -> ModuleResult:
        """Run obstacle course and motor planning - thin adapter."""
        self._set_running(True)
        if self._stop_requested:
            self._set_running(False)
            return ModuleResult(completed=False, engagement=None)
        self._set_running(False)
        return ModuleResult(completed=True, engagement=None)

    def exit(self) -> None:
        """Cleanup obstacle course and motor planning."""
        self.logger.info("Module end: obstacle_course")
