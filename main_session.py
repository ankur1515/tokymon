"""Tokymon Session Orchestrator entrypoint for Raspberry Pi."""
from __future__ import annotations

import signal
import time

from control.safety import SafetyManager
from sessions import SessionOrchestrator
from system.config import CONFIG
from system.logger import get_logger
from system.mqtt_bus import MqttBus

LOGGER = get_logger("main_session")

# Dialogue lockdown: STT/LLM bypassed for POC sessions
# STT and LLM code remains but is not used in session flow


def main() -> None:
    """Main entry point for Session Orchestrator mode."""
    LOGGER.info(
        "Tokymon Session Orchestrator starting (simulator=%s)",
        CONFIG["services"]["runtime"]["use_simulator"],
    )

    # Initialize system components
    mqtt = MqttBus()
    mqtt.start()

    safety = SafetyManager()
    safety.start()

    # Create Session Orchestrator
    orchestrator = SessionOrchestrator(
        safety_manager=safety,
        max_modules_per_session=CONFIG.get("sessions", {}).get("max_modules_per_session", 3),
    )

    # Signal handlers for graceful shutdown
    stop_requested = False

    def handle_signal(signum, _frame):  # type: ignore[override]
        nonlocal stop_requested
        LOGGER.info("Signal %s received, shutting down session", signum)
        stop_requested = True
        orchestrator.stop()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        # Get module selection from config or use defaults
        selected_modules = CONFIG.get("sessions", {}).get("selected_modules")
        if selected_modules is None:
            # Use first N modules by default
            selected_modules = None  # Will use max_modules_per_session

        # Start session
        session_id = orchestrator.start_session(selected_modules=selected_modules)
        LOGGER.info("Session started: %s", session_id)

        # Publish session start to MQTT
        mqtt.publish("session/start", session_id)

        # Main FSM loop
        loop_count = 0
        while orchestrator.is_session_active() and not stop_requested:
            result = orchestrator.run()

            # Publish session state updates
            if loop_count % 10 == 0:  # Every 10 iterations
                state = orchestrator.get_state().value
                mqtt.publish("session/state", state)
                safety.heartbeat()

            loop_count += 1
            time.sleep(0.1)  # Small delay to prevent tight loop

        # Get final results
        final_results = orchestrator.get_session_results()
        LOGGER.info("Session completed: %s", final_results["state"])
        LOGGER.info("Modules run: %s", final_results["modules_run"])
        LOGGER.info("Session duration: %.2f seconds", final_results["session_duration"])

        # Publish session end to MQTT
        mqtt.publish("session/end", session_id)
        mqtt.publish("session/results", str(final_results))

        # Log execution summary (simplified)
        for log_entry in final_results["execution_log"]:
            LOGGER.info(
                "Module %s: completed=%s",
                log_entry["module_name"],
                log_entry["completed"],
            )

    except KeyboardInterrupt:
        LOGGER.warning("Keyboard interrupt received")
        orchestrator.emergency_stop()
        safety.emergency_stop()
    except Exception as exc:
        LOGGER.exception("Fatal error in session orchestrator: %s", exc)
        orchestrator.emergency_stop()
        safety.emergency_stop()
    finally:
        # Cleanup - graceful shutdown on normal completion
        if orchestrator.get_state().value == "session_end":
            safety.stop()  # Graceful stop on normal completion
        else:
            safety.emergency_stop()  # Emergency stop if session didn't complete normally
        mqtt.stop()
        LOGGER.info("Tokymon Session Orchestrator stopped")


if __name__ == "__main__":
    main()

