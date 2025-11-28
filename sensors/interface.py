"""Sensor factory that switches between real and simulated drivers."""
from __future__ import annotations

from sensors.drivers import hcsr04, ir_left, ir_right
from sensors import simulator
from system.config import CONFIG

USE_SIM = CONFIG["services"]["runtime"].get("use_simulator", False)


def get_ultrasonic_reader():
    if USE_SIM:
        return simulator.read_distance_cm
    return hcsr04.measure_distance_cm


def get_ir_left_reader():
    if USE_SIM:
        return lambda: simulator.read_ir("left")
    return ir_left.read_state


def get_ir_right_reader():
    if USE_SIM:
        return lambda: simulator.read_ir("right")
    return ir_right.read_state
