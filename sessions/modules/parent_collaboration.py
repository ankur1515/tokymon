"""Parent & Therapist Collaboration module."""
from __future__ import annotations

from sessions.modules.base import BaseModule, ModuleResult


class ParentCollaborationModule(BaseModule):
    """Module 9: Parent & Therapist Collaboration - Thin adapter."""

    def __init__(self) -> None:
        super().__init__("parent_collaboration")

    def enter(self) -> None:
        """Initialize parent and therapist collaboration."""
        self.logger.info("Module start: parent_collaboration")

    def run(self) -> ModuleResult:
        """Run parent and therapist collaboration - thin adapter."""
        self._set_running(True)
        if self._stop_requested:
            self._set_running(False)
            return ModuleResult(completed=False, engagement=None)
        self._set_running(False)
        return ModuleResult(completed=True, engagement=None)

    def exit(self) -> None:
        """Cleanup parent and therapist collaboration."""
        self.logger.info("Module end: parent_collaboration")
