"""MAX7219 LED matrix driver (stub)."""
from __future__ import annotations

from system.config import CONFIG
from system.logger import get_logger

LOGGER = get_logger("max7219")
SPI = CONFIG["pinmap"]["led_matrix"]["spi"]

EXPRESSIONS = {
    "idle": [0x00] * 8,
    "smile": [0x3c, 0x42, 0xa5, 0x81, 0xa5, 0x99, 0x42, 0x3c],
}


def init_display() -> None:
    LOGGER.info(
        "Init MAX7219 via MOSI=%s CLK=%s CS=%s", SPI["mosi"], SPI["clk"], SPI["cs"]
    )
    # TODO: Wire up spidev when running on hardware.


def show_expression(name: str) -> None:
    frame = EXPRESSIONS.get(name, EXPRESSIONS["idle"])
    LOGGER.debug("Display expression %s -> %s", name, frame)
    # TODO: Send frame over SPI.
