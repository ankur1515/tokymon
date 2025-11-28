from control import motors
from drivers import rpi_gpio
from system.config import CONFIG


class FakeBackend:
    def __init__(self):
        self.state = {}

    def setup(self, pin, mode):  # pragma: no cover - not used in test
        pass

    def write(self, pin, value):
        self.state[pin] = value

    def read(self, pin):  # pragma: no cover - not used
        return False

    def cleanup(self):  # pragma: no cover
        self.state.clear()


def test_forward_and_stop_sets_pins():
    fake = FakeBackend()
    rpi_gpio.BACKEND = fake
    motors.forward()
    pins = CONFIG["pinmap"]["motors"]
    assert fake.state[pins["motor_a"]["in1"]] is True
    assert fake.state[pins["motor_a"]["in2"]] is False
    motors.stop()
    assert all(value is False for value in fake.state.values())
