"""Base module interface for all session modules."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from system.logger import get_logger

LOGGER = get_logger("session_module")


@dataclass
class ModuleResult:
    """Simple result from module execution."""
    completed: bool
    engagement: Optional[bool] = None  # Binary signal or None


class BaseModule(ABC):
    """
    Base interface for all session modules.
    
    All modules must implement enter(), run(), and exit() methods.
    Modules are passive: they run when called and return control to the orchestrator.
    """

    def __init__(self, module_name: str) -> None:
        self.module_name = module_name
        self.logger = get_logger(f"module.{module_name}")
        self._is_running = False
        self._stop_requested = False

    @abstractmethod
    def enter(self) -> None:
        """
        Called when module is about to start.
        Perform any initialization here.
        """
        pass

    @abstractmethod
    def run(self) -> ModuleResult:
        """
        Main execution logic for the module.
        
        Returns:
            ModuleResult with:
            - completed: bool
            - engagement: bool or None (binary signal)
        
        Note: This method should check self._stop_requested periodically
        and exit gracefully if True.
        """
        pass

    @abstractmethod
    def exit(self) -> None:
        """
        Called when module is finishing.
        Perform any cleanup here.
        """
        pass

    def request_stop(self) -> None:
        """Request the module to stop gracefully."""
        self._stop_requested = True
        self.logger.info("Stop requested for module %s", self.module_name)

    @property
    def is_running(self) -> bool:
        """Check if module is currently running."""
        return self._is_running

    def _set_running(self, value: bool) -> None:
        """Internal method to track running state."""
        self._is_running = value

