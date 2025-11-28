"""Simple supervisor to keep background workers healthy."""
from __future__ import annotations

import threading
import time
from typing import Callable, Dict

from system.logger import get_logger

LOGGER = get_logger("supervisor")


class Supervisor:
    """Spawns worker threads and restarts on failure."""

    def __init__(self) -> None:
        self._workers: Dict[str, threading.Thread] = {}
        self._targets: Dict[str, Callable[[], None]] = {}
        self._stop = threading.Event()

    def register(self, name: str, target: Callable[[], None]) -> None:
        self._targets[name] = target

    def start(self) -> None:
        for name, target in self._targets.items():
            self._spawn(name, target)
        threading.Thread(target=self._watchdog_loop, daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _spawn(self, name: str, target: Callable[[], None]) -> None:
        def runner() -> None:
            LOGGER.info("Worker %s starting", name)
            try:
                target()
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.exception("Worker %s crashed: %s", name, exc)
            finally:
                LOGGER.warning("Worker %s exited", name)

        thread = threading.Thread(target=runner, daemon=True)
        self._workers[name] = thread
        thread.start()

    def _watchdog_loop(self) -> None:
        while not self._stop.is_set():
            for name, thread in list(self._workers.items()):
                if not thread.is_alive():
                    LOGGER.warning("Restarting worker %s", name)
                    self._spawn(name, self._targets[name])
            time.sleep(2)
