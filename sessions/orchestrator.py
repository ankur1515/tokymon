"""Session Orchestrator with Finite State Machine for Tokymon POC."""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from control.safety import SafetyManager
from sessions.modules import MODULE_REGISTRY
from sessions.modules.base import BaseModule, ModuleResult
from system.logger import get_logger

LOGGER = get_logger("orchestrator")


class SessionState(Enum):
    """
    FSM States for Session Orchestrator.
    
    STATE TRANSITION TABLE:
    ======================
    
    IDLE
     → SESSION_START (on start_session())
    
    SESSION_START
     → GREETING (automatic)
    
    GREETING
     → MODULE_SELECT (automatic)
    
    MODULE_SELECT
     → MODULE_RUNNING (when module selected)
     → SESSION_END (if no more modules)
    
    MODULE_RUNNING
     → MODULE_COMPLETE (after module.run() returns)
     → EMERGENCY_STOP (on error or stop_requested)
    
    MODULE_COMPLETE
     → MODULE_SELECT (if more modules)
     → SESSION_END (if all modules done)
    
    EMERGENCY_STOP (reachable from ANY state)
     → SAFE_SHUTDOWN (automatic)
    
    SAFE_SHUTDOWN
     → SESSION_END (automatic)
    
    SESSION_END
     → (terminal state)
    
    EMERGENCY_STOP can be triggered from ANY state via:
    - emergency_stop() method
    - stop() method (sets stop_requested flag)
    - SafetyManager emergency stop
    - Module execution error
    """

    IDLE = "idle"
    SESSION_START = "session_start"
    GREETING = "greeting"
    MODULE_SELECT = "module_select"
    MODULE_RUNNING = "module_running"
    MODULE_COMPLETE = "module_complete"
    SESSION_END = "session_end"
    EMERGENCY_STOP = "emergency_stop"
    SAFE_SHUTDOWN = "safe_shutdown"


class SessionOrchestrator:
    """
    Session Orchestrator using a Finite State Machine.
    
    Coordinates POC modules in a safe, deterministic way.
    The orchestrator is the ONLY component that controls flow.
    Modules are passive: run → return → exit.
    """

    def __init__(
        self,
        safety_manager: Optional[SafetyManager] = None,
        max_modules_per_session: int = 3,
    ) -> None:
        """
        Initialize the Session Orchestrator.
        
        Args:
            safety_manager: Optional SafetyManager instance for emergency stops
            max_modules_per_session: Maximum modules to run per session (default: 3)
        """
        self.safety_manager = safety_manager
        self.max_modules_per_session = max_modules_per_session
        self.logger = get_logger("orchestrator")

        # FSM state
        self.state = SessionState.IDLE
        self._stop_requested = False

        # Session tracking
        self.session_id: Optional[str] = None
        self.session_start_time: Optional[float] = None
        self.modules_completed: List[str] = []
        self.current_module: Optional[BaseModule] = None
        self.current_module_name: Optional[str] = None
        self.module_start_time: Optional[float] = None
        
        # Session limits
        self.max_session_duration_seconds = 15 * 60  # 15 minutes
        self.max_modules_per_session = min(max_modules_per_session, 3)  # Hard limit: 3

        # Module registry
        self._module_instances: Dict[str, BaseModule] = {}
        self._initialize_modules()

        # Execution log (simplified)
        self.execution_log: List[Dict[str, Any]] = []

    def _initialize_modules(self) -> None:
        """Initialize all module instances."""
        for module_name, module_class in MODULE_REGISTRY:
            self._module_instances[module_name] = module_class()
        self.logger.info("Initialized %d modules", len(self._module_instances))

    def start_session(self, selected_modules: Optional[List[str]] = None) -> str:
        """
        Start a new session.
        
        Args:
            selected_modules: Optional list of module names to run.
                            If None, selects first max_modules_per_session modules.
        
        Returns:
            session_id: Unique session identifier
        """
        if self.state != SessionState.IDLE:
            raise RuntimeError(
                f"Cannot start session: current state is {self.state.value}"
            )

        self.session_id = str(uuid.uuid4())
        self.session_start_time = time.time()
        self.modules_completed = []
        self.execution_log = []
        self._stop_requested = False

        # Select modules
        if selected_modules is None:
            # Default: first N modules
            selected_modules = [
                name for name, _ in MODULE_REGISTRY[: self.max_modules_per_session]
            ]
        else:
            # Validate and enforce max 3 modules
            if len(selected_modules) > 3:
                self.logger.warning("More than 3 modules requested, limiting to 3")
                selected_modules = selected_modules[:3]
            # Validate module names
            available = {name for name, _ in MODULE_REGISTRY}
            invalid = set(selected_modules) - available
            if invalid:
                raise ValueError(f"Invalid module names: {invalid}")

        self.logger.info(
            "Starting session %s with modules: %s", self.session_id, selected_modules
        )

        # Transition to SESSION_START
        self._transition_to(SessionState.SESSION_START)
        self._selected_modules = selected_modules
        self._module_index = 0

        return self.session_id

    def run(self) -> Dict[str, Any]:
        """
        Run the orchestrator FSM loop.
        
        This method should be called in a loop until the session completes.
        
        Returns:
            Dict with session results:
            - session_id: str
            - completed: bool
            - modules_run: List[str]
            - execution_log: List[Dict]
        """
        if self.state == SessionState.IDLE:
            self.logger.warning("Session not started. Call start_session() first.")
            return self._get_session_results()

        # Check for emergency stop
        if self._stop_requested:
            self._handle_emergency_stop()
            return self._get_session_results()
        
        # Check session duration limit
        if self.session_start_time:
            elapsed = time.time() - self.session_start_time
            if elapsed > self.max_session_duration_seconds:
                self.logger.warning("Session duration limit exceeded (15 min), ending session")
                self._stop_requested = True
                self._handle_emergency_stop()
                return self._get_session_results()

        # FSM state machine
        if self.state == SessionState.SESSION_START:
            self._handle_session_start()
        elif self.state == SessionState.GREETING:
            self._handle_greeting()
        elif self.state == SessionState.MODULE_SELECT:
            self._handle_module_select()
        elif self.state == SessionState.MODULE_RUNNING:
            self._handle_module_running()
        elif self.state == SessionState.MODULE_COMPLETE:
            self._handle_module_complete()
        elif self.state == SessionState.EMERGENCY_STOP:
            self._handle_emergency_stop()
        elif self.state == SessionState.SAFE_SHUTDOWN:
            self._handle_safe_shutdown()
        elif self.state == SessionState.SESSION_END:
            # Session already ended
            pass

        return self._get_session_results()

    def stop(self) -> None:
        """
        Request immediate stop of the session.
        Triggers emergency stop from any state.
        """
        self.logger.warning("Stop requested by parent")
        self._stop_requested = True
        if self.current_module:
            self.current_module.request_stop()

    def emergency_stop(self) -> None:
        """
        Emergency stop - immediately halt all operations.
        Can be called from any state.
        """
        self.logger.error("EMERGENCY STOP triggered")
        self._stop_requested = True
        if self.current_module:
            self.current_module.request_stop()
        if self.safety_manager:
            self.safety_manager.emergency_stop()
        self._transition_to(SessionState.EMERGENCY_STOP)

    def _transition_to(self, new_state: SessionState) -> None:
        """Transition to a new FSM state."""
        old_state = self.state
        self.state = new_state
        self.logger.debug(
            "State transition: %s → %s", old_state.value, new_state.value
        )

    def _handle_session_start(self) -> None:
        """Handle SESSION_START state."""
        self.logger.info("Session %s started", self.session_id)
        self._transition_to(SessionState.GREETING)
    
    def _handle_greeting(self) -> None:
        """Handle GREETING state - play greeting audio."""
        self.logger.info("Session greeting")
        # Greeting handled by orchestrator, not a module
        # Transition directly to module selection
        self._transition_to(SessionState.MODULE_SELECT)

    def _handle_module_select(self) -> None:
        """Handle MODULE_SELECT state."""
        if self._module_index >= len(self._selected_modules):
            # All modules completed
            self._transition_to(SessionState.SESSION_END)
            return

        module_name = self._selected_modules[self._module_index]
        self.current_module_name = module_name
        self.current_module = self._module_instances[module_name]

        self.logger.info("Selected module: %s", module_name)
        self._transition_to(SessionState.MODULE_RUNNING)

    def _handle_module_running(self) -> None:
        """Handle MODULE_RUNNING state."""
        if not self.current_module:
            self.logger.error("No current module in MODULE_RUNNING state")
            self._transition_to(SessionState.EMERGENCY_STOP)
            return

        # Enter module
        try:
            self.current_module.enter()
            self.module_start_time = time.time()

            # Run module
            result = self.current_module.run()
            
            # Ensure result is ModuleResult
            if isinstance(result, ModuleResult):
                module_result = result
            else:
                # Legacy dict format - convert
                module_result = ModuleResult(
                    completed=result.get("completed", False),
                    engagement=result.get("child_engagement") or result.get("engagement")
                )

            # Exit module
            self.current_module.exit()

            # Log execution (simplified schema)
            execution_time = time.time() - self.module_start_time
            log_entry = {
                "module_name": self.current_module_name,
                "start_time": self.module_start_time,
                "end_time": time.time(),
                "completed": module_result.completed,
            }
            self.execution_log.append(log_entry)
            self.logger.info(
                "Module %s completed: %s",
                self.current_module_name,
                module_result.completed,
            )

            # Track completion
            if module_result.completed:
                self.modules_completed.append(self.current_module_name)

            # Transition to MODULE_COMPLETE
            self._transition_to(SessionState.MODULE_COMPLETE)

        except Exception as exc:
            self.logger.exception("Error running module %s: %s", self.current_module_name, exc)
            # Log failed execution (simplified)
            log_entry = {
                "module_name": self.current_module_name,
                "start_time": self.module_start_time or time.time(),
                "end_time": time.time(),
                "completed": False,
            }
            self.execution_log.append(log_entry)
            self._transition_to(SessionState.EMERGENCY_STOP)

        finally:
            self.current_module = None
            self.current_module_name = None
            self.module_start_time = None

    def _handle_module_complete(self) -> None:
        """Handle MODULE_COMPLETE state."""
        self._module_index += 1

        # Check if more modules to run
        if self._module_index < len(self._selected_modules):
            self._transition_to(SessionState.MODULE_SELECT)
        else:
            # All modules done
            self._transition_to(SessionState.SESSION_END)

    def _handle_emergency_stop(self) -> None:
        """Handle EMERGENCY_STOP state."""
        self.logger.error("Emergency stop active")
        
        # Stop current module if running
        if self.current_module:
            try:
                self.current_module.request_stop()
                self.current_module.exit()
            except Exception as exc:
                self.logger.exception("Error during module cleanup: %s", exc)

        # Log emergency stop (simplified)
        if self.current_module_name and self.module_start_time:
            log_entry = {
                "module_name": self.current_module_name,
                "start_time": self.module_start_time,
                "end_time": time.time(),
                "completed": False,
            }
            self.execution_log.append(log_entry)

        self._transition_to(SessionState.SAFE_SHUTDOWN)

    def _handle_safe_shutdown(self) -> None:
        """Handle SAFE_SHUTDOWN state."""
        self.logger.info("Performing safe shutdown")
        
        # Ensure all motors stopped
        if self.safety_manager:
            self.safety_manager.emergency_stop()

        self._transition_to(SessionState.SESSION_END)

    def get_session_results(self) -> Dict[str, Any]:
        """Get current session results."""
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "completed": self.state == SessionState.SESSION_END,
            "modules_run": self.modules_completed.copy(),
            "execution_log": self.execution_log.copy(),
            "session_duration": (
                time.time() - self.session_start_time
                if self.session_start_time
                else 0.0
            ),
        }

    def _get_session_results(self) -> Dict[str, Any]:
        """Internal alias for get_session_results()."""
        return self.get_session_results()

    def is_session_active(self) -> bool:
        """Check if session is currently active."""
        return self.state not in (
            SessionState.IDLE,
            SessionState.SESSION_END,
        )

    def get_state(self) -> SessionState:
        """Get current FSM state."""
        return self.state

