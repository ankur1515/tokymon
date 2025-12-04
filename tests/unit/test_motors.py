from control import motors
from system.config import CONFIG


class FakeLGPIO:
    """Mock lgpio for testing."""
    LOW = 0
    HIGH = 1
    
    def __init__(self):
        self.state = {}
        self.chip_handle = 1
    
    def gpiochip_open(self, chip):
        return self.chip_handle
    
    def gpio_claim_output(self, handle, pin):
        self.state[pin] = self.LOW
    
    def gpio_write(self, handle, pin, value):
        self.state[pin] = value
    
    def tx_pwm(self, handle, pin, frequency, duty_cycle):
        # PWM is tested via motor speed calls
        pass
    
    def gpiochip_close(self, handle):
        pass


def test_forward_and_stop_sets_pins():
    """Test TB6612 motor control with Motor A polarity fix."""
    import control.motors as motors_module
    import sys
    
    # Mock lgpio
    fake_lgpio = FakeLGPIO()
    original_lgpio = sys.modules.get('lgpio')
    sys.modules['lgpio'] = fake_lgpio
    motors_module.GPIO = fake_lgpio
    motors_module.LGPIO_AVAILABLE = True
    
    # Reset driver singleton
    motors_module._driver = None
    
    # Force non-simulator mode
    original_sim = motors_module.USE_SIM
    motors_module.USE_SIM = False
    
    try:
        motors.forward()
        # TB6612 Motor A: AIN1=LOW (0), AIN2=HIGH (1) for forward
        # TB6612 Motor B: BIN1=HIGH (1), BIN2=LOW (0) for forward
        assert motors_module.AIN1_PIN in fake_lgpio.state
        assert motors_module.AIN2_PIN in fake_lgpio.state
        assert fake_lgpio.state[motors_module.AIN1_PIN] == fake_lgpio.LOW  # Motor A polarity fix
        assert fake_lgpio.state[motors_module.AIN2_PIN] == fake_lgpio.HIGH
        assert fake_lgpio.state[motors_module.BIN1_PIN] == fake_lgpio.HIGH
        assert fake_lgpio.state[motors_module.BIN2_PIN] == fake_lgpio.LOW
        
        motors.stop()
        # After stop (coast), all direction pins should be LOW
        assert fake_lgpio.state[motors_module.AIN1_PIN] == fake_lgpio.LOW
        assert fake_lgpio.state[motors_module.AIN2_PIN] == fake_lgpio.LOW
        assert fake_lgpio.state[motors_module.BIN1_PIN] == fake_lgpio.LOW
        assert fake_lgpio.state[motors_module.BIN2_PIN] == fake_lgpio.LOW
    finally:
        motors_module.USE_SIM = original_sim
        motors_module._driver = None
        if original_lgpio:
            sys.modules['lgpio'] = original_lgpio
        elif 'lgpio' in sys.modules:
            del sys.modules['lgpio']
