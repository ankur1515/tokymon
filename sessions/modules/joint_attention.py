"""Joint Attention & Engagement module."""
from __future__ import annotations

from sessions.modules.base import BaseModule, ModuleResult


class JointAttentionModule(BaseModule):
    """Module 5: Joint Attention & Engagement - Thin adapter."""

    def __init__(self) -> None:
        super().__init__("joint_attention")

    def enter(self) -> None:
        """Initialize joint attention and engagement."""
        self.logger.info("Module start: joint_attention")

    def run(self) -> ModuleResult:
        """Run joint attention and engagement - thin adapter."""
        self._set_running(True)
        if self._stop_requested:
            self._set_running(False)
            return ModuleResult(completed=False, engagement=None)
        self._set_running(False)
        return ModuleResult(completed=True, engagement=None)

    def exit(self) -> None:
        """Cleanup joint attention and engagement."""
        self.logger.info("Module end: joint_attention")
