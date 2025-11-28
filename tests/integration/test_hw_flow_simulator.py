import os

from examples import hw_test
from system.config import CONFIG


def test_hw_flow_runs_in_simulator(monkeypatch):
    monkeypatch.setenv("TOKY_ENV", "dev")
    CONFIG["services"]["runtime"]["use_simulator"] = True
    report = hw_test.run_hw_flow(run_hw=True, auto_confirm=True)
    assert report["hardware_enabled"] is False or report["env"] != "prod"
    assert "steps" in report
