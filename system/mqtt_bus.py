"""MQTT event bus wrapper."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Dict, Protocol

from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("mqtt")


class _ClientProtocol(Protocol):
    def connect(self, host: str, port: int, keepalive: int) -> int: ...
    def loop_forever(self) -> None: ...
    def publish(self, topic: str, payload: str) -> None: ...
    def subscribe(self, topic: str) -> None: ...
    def disconnect(self) -> None: ...
    on_connect: Callable[..., None]
    on_message: Callable[..., None]


@dataclass
class _MockClient:
    on_connect: Callable[..., None] = lambda *args, **kwargs: None
    on_message: Callable[..., None] = lambda *args, **kwargs: None

    def connect(self, host: str, port: int, keepalive: int) -> int:  # pragma: no cover - simple mock
        LOGGER.info("Mock MQTT connect %s:%s", host, port)
        return 0

    def loop_forever(self) -> None:  # pragma: no cover - mock does nothing
        return None

    def publish(self, topic: str, payload: str) -> None:
        LOGGER.info("Mock MQTT publish %s => %s", topic, payload)

    def subscribe(self, topic: str) -> None:
        LOGGER.info("Mock MQTT subscribe %s", topic)

    def disconnect(self) -> None:
        LOGGER.info("Mock MQTT disconnect")


def _build_client() -> _ClientProtocol:
    if CONFIG["services"]["runtime"].get("use_simulator", False):
        return _MockClient()
    import paho.mqtt.client as mqtt  # type: ignore

    client: _ClientProtocol = mqtt.Client()
    return client


class MqttBus:
    def __init__(self) -> None:
        mqtt_cfg = CONFIG["services"].get("mqtt", {})
        host = mqtt_cfg.get("broker", CONFIG["env"]["MQTT_BROKER_HOST"])
        port = mqtt_cfg.get("port", CONFIG["env"]["MQTT_BROKER_PORT"])
        self._client = _build_client()
        self._client.on_connect = self._on_connect
        self._callbacks: Dict[str, Callable[[str], None]] = {}
        self._thread: threading.Thread | None = None
        self._host = host
        self._port = port

    def start(self) -> None:
        LOGGER.info("Starting MQTT bus on %s:%s", self._host, self._port)
        self._client.connect(self._host, self._port, keepalive=60)
        if not isinstance(self._client, _MockClient):
            self._thread = threading.Thread(target=self._client.loop_forever, daemon=True)
            self._thread.start()

    def publish(self, topic: str, payload: str) -> None:
        LOGGER.debug("MQTT publish %s => %s", topic, payload)
        self._client.publish(topic, payload)

    def subscribe(self, topic: str, handler: Callable[[str], None]) -> None:
        LOGGER.info("MQTT subscribe %s", topic)
        self._callbacks[topic] = handler
        self._client.subscribe(topic)

    def stop(self) -> None:
        LOGGER.info("Stopping MQTT bus")
        self._client.disconnect()

    # pylint: disable=unused-argument
    def _on_connect(self, client, userdata, flags, rc):  # type: ignore[override]
        LOGGER.info("MQTT connected with rc=%s", rc)
        for topic in self._callbacks:
            self._client.subscribe(topic)
        self._client.on_message = self._on_message

    def _on_message(self, _client, _userdata, msg):
        payload = getattr(msg, "payload", b"").decode("utf-8")
        topic = getattr(msg, "topic", "")
        handler = self._callbacks.get(topic)
        if handler:
            handler(payload)
        else:
            LOGGER.warning("No handler for topic %s", topic)
