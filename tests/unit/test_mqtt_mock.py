import logging

from system import config
from system.mqtt_bus import MqttBus


def test_mock_publish_logs(caplog):
    caplog.set_level(logging.INFO)
    config.CONFIG["services"]["runtime"]["use_simulator"] = True
    bus = MqttBus()
    bus.start()
    bus.publish("tokymon/test", "ping")
    assert any("Mock MQTT publish" in rec.message for rec in caplog.records)
    bus.stop()
