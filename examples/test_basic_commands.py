"""Test script for basic_commands module on Mac."""
from __future__ import annotations

import sys
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from control.safety import SafetyManager
from sessions import SessionOrchestrator
from system.logger import get_logger

LOGGER = get_logger("test_basic_commands")


def test_basic_commands_module() -> None:
    """Test the basic_commands module in simulator mode."""
    LOGGER.info("=== Testing basic_commands Module ===")
    
    # Initialize safety manager
    safety = SafetyManager()
    safety.start()
    
    # Create orchestrator
    orchestrator = SessionOrchestrator(
        safety_manager=safety,
        max_modules_per_session=1,  # Just test basic_commands
    )
    
    # Start session with only basic_commands
    session_id = orchestrator.start_session(
        selected_modules=["basic_commands"]
    )
    LOGGER.info("Session started: %s", session_id)
    LOGGER.info("iPhone UI available at: http://localhost:8080")
    LOGGER.info("Open that URL in your browser to see the face animation")
    
    # Run FSM loop
    loop_count = 0
    while orchestrator.is_session_active():
        result = orchestrator.run()
        # Send safety heartbeats regularly
        if loop_count % 5 == 0:  # Every 0.5 seconds
            safety.heartbeat()
        loop_count += 1
        time.sleep(0.1)  # Small delay
    
    # Get final results
    final_result = orchestrator.get_session_results()
    LOGGER.info("Session completed: %s", final_result["state"])
    LOGGER.info("Modules run: %s", final_result["modules_run"])
    
    safety.stop()
    LOGGER.info("=== Test Complete ===")


if __name__ == "__main__":
    test_basic_commands_module()

