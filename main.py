"""Tokymon entrypoint."""
from __future__ import annotations

import signal
import threading
import time

from brain import llm_gateway
from control import actuators
from control.safety import SafetyManager
from sensors import interface
from system.config import CONFIG
from system.logger import get_logger
from system.mqtt_bus import MqttBus

LOGGER = get_logger("main")


def main() -> None:
    LOGGER.info("Tokymon starting (simulator=%s)", CONFIG["services"]["runtime"]["use_simulator"])
    stop_event = threading.Event()

    mqtt = MqttBus()
    mqtt.start()

    safety = SafetyManager()
    safety.start()

    ultrasonic = interface.get_ultrasonic_reader()

    def handle_signal(signum, _frame):  # type: ignore[override]
        LOGGER.info("Signal %s received, shutting down", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    heartbeat_interval = CONFIG["services"]["runtime"]["heartbeat_interval_s"]

    while not stop_event.is_set():
        distance = ultrasonic()
        mqtt.publish("system/heartbeat", "alive")
        mqtt.publish("sensors/distance", str(distance))
        safety.heartbeat()
        LOGGER.debug("Distance %.2f cm", distance)
        time.sleep(heartbeat_interval)

    safety.emergency_stop()
    mqtt.stop()
    LOGGER.info("Tokymon stopped")


if __name__ == "__main__":
    main()
