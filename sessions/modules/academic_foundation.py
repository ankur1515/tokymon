"""Academic Foundation module."""
from __future__ import annotations

from sessions.modules.base import BaseModule, ModuleResult


class AcademicFoundationModule(BaseModule):
    """Module 7: Academic Foundation - Thin adapter."""

    def __init__(self) -> None:
        super().__init__("academic_foundation")

    def enter(self) -> None:
        """Initialize academic foundation."""
        self.logger.info("Module start: academic_foundation")

    def run(self) -> ModuleResult:
        """Run academic foundation - thin adapter."""
        self._set_running(True)
        if self._stop_requested:
            self._set_running(False)
            return ModuleResult(completed=False, engagement=None)
        self._set_running(False)
        return ModuleResult(completed=True, engagement=None)

    def exit(self) -> None:
        """Cleanup academic foundation."""
        self.logger.info("Module end: academic_foundation")
