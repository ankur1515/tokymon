"""
Regression test: basic_commands turn_left / turn_right motor pin directions.

The chassis has physically reversed wiring, so the correct pin assignments are:
  turn_left  → A='forward',  B='backward'
  turn_right → A='backward', B='forward'

This test guards against re-introduction of the original inversion bug
(where turn_left set A='backward', B='forward', causing the robot to
physically turn right while saying "turning left").
"""
import unittest
from unittest.mock import patch


class FakeDriver:
    """Records set_direction calls so we can assert pin assignments."""

    def __init__(self):
        self.directions = {}
        self.speed_calls = []
        self.brake_called = False

    def set_direction(self, motor, direction):
        self.directions[motor] = direction

    def set_motor_speed(self, a, b):
        self.speed_calls.append((a, b))

    def forward(self, speed=100):
        pass

    def backward(self, speed=100):
        pass

    def brake(self):
        self.brake_called = True


class TestBasicCommandsTurnDirection(unittest.TestCase):
    """
    Unit tests for the turn_left / turn_right paths in
    sessions.modules.basic_commands._perform_safe_command().

    All I/O (audio, LED, UI, sleep, sensors) is patched out so the test
    runs fast and offline in Mac simulator mode.
    """

    def _run_command(self, command: str) -> FakeDriver:
        """Call _perform_safe_command and return the FakeDriver used."""
        fake_driver = FakeDriver()

        with (
            patch("sessions.modules.basic_commands._play_prompt"),
            patch("sessions.modules.basic_commands._update_ui_face"),
            patch("sessions.modules.basic_commands._show_face_led"),
            patch("sessions.modules.basic_commands._safe_sleep"),
            patch("sessions.modules.basic_commands.motors._get_driver",
                  return_value=fake_driver),
        ):
            from sessions.modules.basic_commands import _perform_safe_command
            _perform_safe_command(command, safety=None)

        return fake_driver

    # ------------------------------------------------------------------
    # turn_left
    # ------------------------------------------------------------------

    def test_turn_left_motor_A_is_forward(self):
        """turn_left must set Motor A to 'forward' (chassis reversed → physical backward for left side)."""
        driver = self._run_command("turn_left")
        self.assertEqual(driver.directions.get('A'), 'forward',
                         "turn_left: Motor A should be 'forward'")

    def test_turn_left_motor_B_is_backward(self):
        """turn_left must set Motor B to 'backward' (chassis reversed → physical forward for right side)."""
        driver = self._run_command("turn_left")
        self.assertEqual(driver.directions.get('B'), 'backward',
                         "turn_left: Motor B should be 'backward'")

    def test_turn_left_not_mirrored_as_right(self):
        """Regression guard: old wrong assignments (A=backward, B=forward) would physically turn RIGHT."""
        driver = self._run_command("turn_left")
        self.assertNotEqual(driver.directions.get('A'), 'backward',
                            "turn_left: A='backward' is the old bug — would physically turn RIGHT")
        self.assertNotEqual(driver.directions.get('B'), 'forward',
                            "turn_left: B='forward' is the old bug — would physically turn RIGHT")

    # ------------------------------------------------------------------
    # turn_right
    # ------------------------------------------------------------------

    def test_turn_right_motor_A_is_backward(self):
        """turn_right must set Motor A to 'backward' (chassis reversed → physical forward for left side)."""
        driver = self._run_command("turn_right")
        self.assertEqual(driver.directions.get('A'), 'backward',
                         "turn_right: Motor A should be 'backward'")

    def test_turn_right_motor_B_is_forward(self):
        """turn_right must set Motor B to 'forward' (chassis reversed → physical backward for right side)."""
        driver = self._run_command("turn_right")
        self.assertEqual(driver.directions.get('B'), 'forward',
                         "turn_right: Motor B should be 'forward'")

    def test_turn_right_not_mirrored_as_left(self):
        """Regression guard: old wrong assignments (A=forward, B=backward) would physically turn LEFT."""
        driver = self._run_command("turn_right")
        self.assertNotEqual(driver.directions.get('A'), 'forward',
                            "turn_right: A='forward' is the old bug — would physically turn LEFT")
        self.assertNotEqual(driver.directions.get('B'), 'backward',
                            "turn_right: B='backward' is the old bug — would physically turn LEFT")

    # ------------------------------------------------------------------
    # Symmetry: turn_left and turn_right must be exact mirrors
    # ------------------------------------------------------------------

    def test_turn_directions_are_opposite(self):
        """turn_left and turn_right must use exactly opposite pin assignments for both motors."""
        left = self._run_command("turn_left")
        right = self._run_command("turn_right")
        opposite = {'forward': 'backward', 'backward': 'forward'}
        for motor in ('A', 'B'):
            self.assertEqual(
                right.directions.get(motor),
                opposite.get(left.directions.get(motor)),
                f"Motor {motor}: turn_right direction should be opposite of turn_left"
            )

    # ------------------------------------------------------------------
    # Sanity: speed and brake
    # ------------------------------------------------------------------

    def test_turn_left_runs_at_full_speed(self):
        driver = self._run_command("turn_left")
        self.assertIn((100, 100), driver.speed_calls,
                      "turn_left should call set_motor_speed(100, 100)")

    def test_turn_right_runs_at_full_speed(self):
        driver = self._run_command("turn_right")
        self.assertIn((100, 100), driver.speed_calls,
                      "turn_right should call set_motor_speed(100, 100)")

    def test_turn_left_brakes_after_move(self):
        driver = self._run_command("turn_left")
        self.assertTrue(driver.brake_called, "turn_left should call brake() after movement")

    def test_turn_right_brakes_after_move(self):
        driver = self._run_command("turn_right")
        self.assertTrue(driver.brake_called, "turn_right should call brake() after movement")


class TestPerform360Rotation(unittest.TestCase):
    """
    Regression tests for _perform_360_rotation pin directions.
    Must use A='forward', B='backward' (physical LEFT turn, same as turn_left).
    """

    def _run_360(self) -> FakeDriver:
        fake_driver = FakeDriver()

        with (
            patch("sessions.modules.basic_commands._update_ui_face"),
            patch("sessions.modules.basic_commands._detect_face_binary", return_value=False),
            patch("sessions.modules.basic_commands._safe_sleep"),
            patch("sessions.modules.basic_commands.motors._get_driver",
                  return_value=fake_driver),
            patch("sessions.modules.basic_commands.motors.reset_to_safe"),
            # Patch time.time so the rotation loop exits immediately
            patch("sessions.modules.basic_commands.time") as mock_time,
        ):
            # First call: start_time=0.0; second+ calls: elapsed > rotation_duration (3.15s)
            mock_time.time.side_effect = [0.0] + [10.0] * 50
            from sessions.modules.basic_commands import _perform_360_rotation
            _perform_360_rotation(safety=None)

        return fake_driver

    def test_360_motor_A_is_forward(self):
        """360° rotation must set Motor A to 'forward' (physical left turn)."""
        driver = self._run_360()
        self.assertEqual(driver.directions.get('A'), 'forward',
                         "360 rotation: Motor A should be 'forward'")

    def test_360_motor_B_is_backward(self):
        """360° rotation must set Motor B to 'backward' (physical left turn)."""
        driver = self._run_360()
        self.assertEqual(driver.directions.get('B'), 'backward',
                         "360 rotation: Motor B should be 'backward'")

    def test_360_matches_turn_left_direction(self):
        """360° rotation pin assignments must match turn_left (both turn physically left)."""
        driver_360 = self._run_360()

        fake_driver = FakeDriver()
        with (
            patch("sessions.modules.basic_commands._play_prompt"),
            patch("sessions.modules.basic_commands._update_ui_face"),
            patch("sessions.modules.basic_commands._show_face_led"),
            patch("sessions.modules.basic_commands._safe_sleep"),
            patch("sessions.modules.basic_commands.motors._get_driver",
                  return_value=fake_driver),
            patch("sessions.modules.basic_commands.motors.reset_to_safe"),
        ):
            from sessions.modules.basic_commands import _perform_safe_command
            _perform_safe_command("turn_left", safety=None)

        self.assertEqual(driver_360.directions.get('A'), fake_driver.directions.get('A'),
                         "360 rotation Motor A must match turn_left Motor A")
        self.assertEqual(driver_360.directions.get('B'), fake_driver.directions.get('B'),
                         "360 rotation Motor B must match turn_left Motor B")


if __name__ == "__main__":
    unittest.main(verbosity=2)
