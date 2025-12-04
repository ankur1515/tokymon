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
    """Test TB6612 motor control with Motor A polarity fix."""
    fake = FakeBackend()
    rpi_gpio.BACKEND = fake
    # Force non-simulator mode for this test
    import control.motors as motors_module
    original_sim = motors_module.USE_SIM
    motors_module.USE_SIM = False
    motors_module._h = None  # Force rpi_gpio fallback
    
    try:
        motors.forward()
        # TB6612 Motor A: AIN1=LOW (False), AIN2=HIGH (True) for forward
        # TB6612 Motor B: BIN1=HIGH (True), BIN2=LOW (False) for forward
        assert motors_module.AIN1_PIN in fake.state
        assert motors_module.AIN2_PIN in fake.state
        assert fake.state[motors_module.AIN1_PIN] is False  # Motor A polarity fix
        assert fake.state[motors_module.AIN2_PIN] is True
        assert fake.state[motors_module.BIN1_PIN] is True
        assert fake.state[motors_module.BIN2_PIN] is False
        
        motors.stop()
        # After stop (coast), all direction pins should be False
        assert fake.state[motors_module.AIN1_PIN] is False
        assert fake.state[motors_module.AIN2_PIN] is False
        assert fake.state[motors_module.BIN1_PIN] is False
        assert fake.state[motors_module.BIN2_PIN] is False
    finally:
        motors_module.USE_SIM = original_sim
