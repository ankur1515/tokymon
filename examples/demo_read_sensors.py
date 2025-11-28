"""Example: read simulator sensors."""
from sensors import interface


if __name__ == "__main__":
    ultrasonic = interface.get_ultrasonic_reader()
    left = interface.get_ir_left_reader()
    right = interface.get_ir_right_reader()
    print("Distance cm:", ultrasonic())
    print("IR left:", left())
    print("IR right:", right())
