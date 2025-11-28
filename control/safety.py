"""Safety watchdogs and emergency stop helpers."""
from __future__ import annotations

import threading
import time
from typing import Callable

from control import motors
from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("safety")


class SafetyManager:
    def __init__(self) -> None:
        runtime = CONFIG["services"]["runtime"]
        self._timeout = runtime["safe_stop_timeout_s"]
        self._heartbeat = time.time()
        self._stop = threading.Event()
        self._callbacks: list[Callable[[], None]] = []

    def start(self) -> None:
        threading.Thread(target=self._monitor, daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        motors.stop()

    def heartbeat(self) -> None:
        self._heartbeat = time.time()

    def register_shutdown(self, callback: Callable[[], None]) -> None:
        self._callbacks.append(callback)

    def emergency_stop(self) -> None:
        LOGGER.error("Emergency stop triggered")
        motors.stop()
        for callback in self._callbacks:
            callback()

    def _monitor(self) -> None:
        while not self._stop.is_set():
            if time.time() - self._heartbeat > self._timeout:
                LOGGER.warning("Watchdog timeout, stopping motors")
                self.emergency_stop()
                self._heartbeat = time.time()
            time.sleep(0.5)
