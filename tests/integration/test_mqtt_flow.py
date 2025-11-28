import types

from system import mqtt_bus


class DummyClient:
    def __init__(self):
        self.published = []
        self.subscriptions = []
        self.on_message = None

    def connect(self, *args, **kwargs):
        return 0

    def loop_forever(self):  # pragma: no cover - no real loop
        return None

    def publish(self, topic, payload):
        self.published.append((topic, payload))

    def subscribe(self, topic):
        self.subscriptions.append(topic)

    def disconnect(self):
        return 0


def test_publish_and_handler(monkeypatch):
    dummy = DummyClient()
    monkeypatch.setattr(mqtt_bus, "_build_client", lambda: dummy)
    bus = mqtt_bus.MqttBus()
    bus.start()
    seen = {}

    def handler(payload):
        seen["payload"] = payload

    bus.subscribe("test/topic", handler)
    message = types.SimpleNamespace(payload=b"hello", topic="test/topic")
    bus._on_connect(None, None, None, 0)
    bus._on_message(None, None, message)
    bus.publish("system/heartbeat", "alive")
    assert seen["payload"] == "hello"
    assert dummy.published[0] == ("system/heartbeat", "alive")
