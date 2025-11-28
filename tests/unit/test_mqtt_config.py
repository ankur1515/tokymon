from system.config import CONFIG


def test_config_contains_mqtt_block():
    mqtt_cfg = CONFIG["services"].get("mqtt")
    assert mqtt_cfg is not None
    assert mqtt_cfg["broker"] == "localhost"
    assert mqtt_cfg["topic_prefix"] == "tokymon"
