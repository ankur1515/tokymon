"""Environment Orientation module."""
from __future__ import annotations

from sessions.modules.base import BaseModule, ModuleResult


class EnvironmentOrientationModule(BaseModule):
    """Module 2: Environment Orientation - Thin adapter."""

    def __init__(self) -> None:
        super().__init__("environment_orientation")

    def enter(self) -> None:
        """Initialize environment orientation."""
        self.logger.info("Module start: environment_orientation")

    def run(self) -> ModuleResult:
        """Run environment orientation - thin adapter."""
        self._set_running(True)
        if self._stop_requested:
            self._set_running(False)
            return ModuleResult(completed=False, engagement=None)
        self._set_running(False)
        return ModuleResult(completed=True, engagement=None)

    def exit(self) -> None:
        """Cleanup environment orientation."""
        self.logger.info("Module end: environment_orientation")

