"""Utility script to calibrate HC-SR04 offset."""
from sensors.interface import get_ultrasonic_reader

if __name__ == "__main__":
    reader = get_ultrasonic_reader()
    for _ in range(5):
        print("Distance cm", reader())
