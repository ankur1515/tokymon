"""Example usage of Session Orchestrator."""
from __future__ import annotations

import time

from control.safety import SafetyManager
from sessions import SessionOrchestrator
from system.logger import get_logger

LOGGER = get_logger("session_example")


def example_session_2_modules() -> None:
    """Example: Run a session with 2 modules."""
    LOGGER.info("=== Example: 2-Module Session ===")

    # Initialize safety manager
    safety = SafetyManager()
    safety.start()

    # Create orchestrator
    orchestrator = SessionOrchestrator(
        safety_manager=safety, max_modules_per_session=2
    )

    # Start session with specific modules
    session_id = orchestrator.start_session(
        selected_modules=["object_identification", "environment_orientation"]
    )
    LOGGER.info("Session started: %s", session_id)

    # Run FSM loop
    while orchestrator.is_session_active():
        result = orchestrator.run()
        time.sleep(0.1)  # Small delay to prevent tight loop

    # Get final results
    final_result = orchestrator.get_session_results()
    LOGGER.info("Session completed: %s", final_result)
    LOGGER.info("Modules run: %s", final_result["modules_run"])
    LOGGER.info("Execution log entries: %d", len(final_result["execution_log"]))

    safety.stop()


def example_session_3_modules() -> None:
    """Example: Run a session with 3 modules."""
    LOGGER.info("=== Example: 3-Module Session ===")

    # Initialize safety manager
    safety = SafetyManager()
    safety.start()

    # Create orchestrator
    orchestrator = SessionOrchestrator(
        safety_manager=safety, max_modules_per_session=3
    )

    # Start session (will use first 3 modules by default)
    session_id = orchestrator.start_session()
    LOGGER.info("Session started: %s", session_id)

    # Run FSM loop
    while orchestrator.is_session_active():
        result = orchestrator.run()
        time.sleep(0.1)

    # Get final results
    final_result = orchestrator.get_session_results()
    LOGGER.info("Session completed: %s", final_result)
    LOGGER.info("Modules run: %s", final_result["modules_run"])

    safety.stop()


def example_emergency_stop() -> None:
    """Example: Emergency stop during session."""
    LOGGER.info("=== Example: Emergency Stop ===")

    # Initialize safety manager
    safety = SafetyManager()
    safety.start()

    # Create orchestrator
    orchestrator = SessionOrchestrator(
        safety_manager=safety, max_modules_per_session=3
    )

    # Start session
    session_id = orchestrator.start_session()
    LOGGER.info("Session started: %s", session_id)

    # Run for a bit, then emergency stop
    iterations = 0
    while orchestrator.is_session_active() and iterations < 10:
        result = orchestrator.run()
        iterations += 1
        time.sleep(0.1)

        # Trigger emergency stop after a few iterations
        if iterations == 5:
            LOGGER.warning("Triggering emergency stop")
            orchestrator.emergency_stop()

    # Continue until session ends
    while orchestrator.is_session_active():
        result = orchestrator.run()
        time.sleep(0.1)

    # Get final results
    final_result = orchestrator.get_session_results()
    LOGGER.info("Session ended: %s", final_result["state"])
    LOGGER.info("Execution log entries: %d", len(final_result["execution_log"]))

    safety.stop()


if __name__ == "__main__":
    # Run examples
    example_session_2_modules()
    print("\n" + "=" * 50 + "\n")
    example_session_3_modules()
    print("\n" + "=" * 50 + "\n")
    example_emergency_stop()

