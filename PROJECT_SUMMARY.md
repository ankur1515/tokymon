# Tokymon Project - Complete Summary

## 📁 Complete Folder Structure

```
tokymon/
├── brain/                          # AI/LLM integration layer
│   ├── __init__.py
│   ├── intent_parser.py           # Parses user intents from speech/text
│   ├── llm_gateway.py             # LLM API integration (OpenAI, etc.)
│   ├── policy_engine.py           # Safety policy enforcement
│   └── state_manager.py           # Robot state management
│
├── configs/                        # Configuration files (YAML)
│   ├── env.dev.yaml               # Development environment config
│   ├── env.prod.yaml              # Production environment config
│   ├── pinmap_pi.yaml             # Hardware pin mappings (BCM GPIO)
│   └── services.yaml              # Service configurations (LLM, STT, TTS, MQTT)
│
├── control/                        # Motor and actuator control
│   ├── __init__.py
│   ├── actuators.py               # Actuator abstractions
│   ├── motors.py                  # TB6612 motor driver (forward, backward, turn)
│   ├── pwm_helpers.py             # PWM control utilities
│   └── safety.py                  # Safety manager with watchdog timers
│
├── data/                           # Runtime data storage
│   ├── photos/                    # Camera capture outputs
│   └── reports/                   # Hardware test reports (JSON)
│
├── display/                        # LED matrix display (MAX7219)
│   ├── __init__.py
│   ├── expressions.py            # Face expressions (eyes, mouth, animations)
│   └── max7219_driver.py         # SPI driver with auto-detection & image rotation
│
├── drivers/                        # Low-level hardware drivers
│   ├── __init__.py
│   ├── rpi_gpio.py               # GPIO abstraction (SafeGPIO for Pi 5)
│   ├── safe_gpio.py              # SafeGPIO wrapper (lgpio for Pi 5)
│   └── sysfs_gpio.py             # Sysfs GPIO backend (legacy)
│
├── examples/                       # Example scripts and hardware tests
│   ├── __init__.py
│   ├── demo_read_sensors.py      # Simple sensor reading demo
│   ├── demo_speech_move.py       # Speech-to-movement demo
│   ├── full_hw_test.py           # Complete hardware auto-test (LED, audio, camera, sensors, motors)
│   ├── hw_test.py                # Basic hardware test
│   └── hw_test_helpers.py        # Test utilities
│
├── models/                         # ML models (placeholder)
│
├── prompts/                        # LLM prompt templates
│   ├── intent_to_action.tpl      # Intent parsing prompt
│   └── system_prompt.txt         # System context for LLM
│
├── raw_scripts/                    # Original working scripts (reference)
│   ├── ir_detect_5s_led.py       # IR sensor + LED test
│   ├── toky_voice.py             # Voice synthesis test
│   ├── tokymon_dual_control.py   # Dual motor control test
│   ├── tokymon_max7219_faces_round_eyes_central.py  # Face expressions
│   └── ultrasonic_test.py        # HC-SR04 ultrasonic test
│
├── scripts/                        # Deployment and utility scripts
│   ├── deploy_to_pi.sh           # Deploy code to Raspberry Pi
│   ├── full_hw_test_run.sh       # Run full hardware test
│   ├── hw_test_run.sh            # Run basic hardware test
│   ├── install_requirements.sh   # Install Python dependencies
│   ├── run_tokymon.sh            # Main entrypoint script
│   ├── setup_venv.sh             # Virtual environment setup
│   └── tokymon.service           # Systemd service file
│
├── sensors/                        # Sensor drivers and interface
│   ├── __init__.py
│   ├── interface.py              # Sensor interface abstraction
│   ├── simulator.py              # Simulator mode for sensors
│   └── drivers/
│       ├── hcsr04.py             # HC-SR04 ultrasonic sensor (Pi 5 compatible)
│       ├── ir_left.py            # Left IR sensor
│       ├── ir_right.py           # Right IR sensor
│       └── ir_sensor.py          # IR sensor interface
│
├── system/                         # Core system utilities
│   ├── __init__.py
│   ├── config.py                 # Centralized config loader (YAML + .env)
│   ├── logger.py                 # Logging setup
│   ├── mqtt_bus.py               # MQTT message bus (with simulator mock)
│   └── supervisor.py             # System supervisor
│
├── tests/                          # Test suite
│   ├── integration/
│   │   ├── test_hw_flow_simulator.py  # Hardware flow integration test
│   │   └── test_mqtt_flow.py          # MQTT integration test
│   └── unit/
│       ├── test_hcsr04.py        # Ultrasonic sensor unit test
│       ├── test_motors.py        # Motor driver unit test
│       ├── test_mqtt_config.py   # MQTT config test
│       └── test_mqtt_mock.py     # MQTT mock test
│
├── tools/                          # Utility tools
│   └── calibrate_hcsr04.py       # Ultrasonic sensor calibration
│
├── vision/                         # Camera and vision processing
│   ├── __init__.py
│   └── camera.py                 # Camera capture (libcamera/rpicam)
│
├── voice/                          # Speech input/output
│   ├── __init__.py
│   ├── audio.py                  # Audio I/O utilities
│   ├── stt.py                    # Speech-to-text (Whisper, etc.)
│   └── tts.py                    # Text-to-speech (espeak + aplay)
│
├── voice_prompts/                  # Voice prompt templates
│
├── main.py                         # Main entrypoint
├── README.md                       # Project documentation
├── requirements.txt                # Python dependencies
├── pyproject.toml                  # Project metadata
└── LICENSE                         # License file
```

---

## 🎯 What We've Built

### **Tokymon** - A Raspberry Pi 5 Robot Framework

A complete, production-ready robot control framework with:
- **Hardware abstraction** for sensors, motors, displays, audio, and camera
- **Simulator mode** for development without hardware
- **Safety-first design** with watchdog timers and policy enforcement
- **Config-driven architecture** for easy customization
- **Comprehensive hardware testing** suite

---

## 🔧 What We've Done & Why

### 1. **Project Structure & Configuration System**

**Files Created:**
- `system/config.py` - Centralized configuration loader
- `configs/pinmap_pi.yaml` - Hardware pin mappings
- `configs/services.yaml` - Service configurations
- `configs/env.dev.yaml` & `configs/env.prod.yaml` - Environment-specific configs

**Why:**
- **Single source of truth** for all hardware pins and settings
- **Environment-aware** (dev vs prod) for simulator vs real hardware
- **Easy deployment** - change configs without code changes
- **Path detection** - automatically detects Mac dev vs Pi production paths

**Key Features:**
- Loads YAML configs with deep merging
- Reads `.env` files for secrets (API keys)
- Auto-detects root path (`/Users/ankursharma/Documents/Dev Projects/tokymon` on Mac, `/home/ankursharma/Projects/tokymon` on Pi)

---

### 2. **Raspberry Pi 5 GPIO Compatibility**

**Files Modified:**
- `drivers/rpi_gpio.py` - GPIO abstraction layer
- `drivers/safe_gpio.py` - SafeGPIO wrapper using `lgpio`
- `drivers/sysfs_gpio.py` - Sysfs backend (legacy)

**Why:**
- **Raspberry Pi 5 is NOT compatible with RPi.GPIO** (legacy library)
- Pi 5 uses new GPIO chip architecture requiring `lgpio` library
- **Global GPIO offset** needed: BCM pin + 559 (or 569) = global GPIO number

**Solution:**
- Always use `SafeGPIO` backend (lgpio-based) for Pi 5
- Convert BCM pins to global GPIO numbers automatically
- Fallback to sysfs for older Pi models
- Simulator mode uses no-op mocks

**Example:**
```python
# BCM pin 23 → Global GPIO 582 (23 + 559)
# BCM pin 24 → Global GPIO 583 (24 + 559)
```

---

### 3. **Motor Driver: L298 → TB6612 Migration**

**Files Modified:**
- `control/motors.py` - Complete rewrite for TB6612 driver
- `configs/pinmap_pi.yaml` - Updated pin mappings
- `tests/unit/test_motors.py` - Updated unit tests

**Why:**
- **TB6612 is more efficient** than L298 (lower power consumption, better PWM control)
- **Smaller form factor** - better for compact robots
- **Built-in protection** - thermal shutdown, overcurrent protection

**Key Changes:**
- Replaced L298 pin structure with TB6612 (AIN1, AIN2, BIN1, BIN2, PWMA, PWMB, STBY)
- Fixed polarity issues (motor A direction inverted)
- Uses `lgpio` for PWM control (Pi 5 compatible)
- Maintains same public API: `forward()`, `backward()`, `turn_left()`, `turn_right()`, `stop()`

**Pin Mapping:**
- Motor A: AIN1=5, AIN2=6, PWMA=12
- Motor B: BIN1=20, BIN2=21, PWMB=13
- Standby: STBY=22

---

### 4. **Ultrasonic Sensor (HC-SR04) - Pi 5 Compatible**

**Files Modified:**
- `sensors/drivers/hcsr04.py` - Complete rewrite
- `sensors/interface.py` - Updated interface

**Why:**
- **Pi 5 GPIO changes** require global GPIO numbers, not BCM
- **Voltage divider** needed for 5V echo signal → 3.3V Pi input
- **Timing precision** critical for accurate distance measurement

**Solution:**
- Uses global GPIO numbers (582, 583) instead of BCM (23, 24)
- Proper timing with `time.sleep()` and `time.time()` for pulse measurement
- Simulator mode returns mock distances
- Error handling for timeout/no-echo scenarios

**Formula:**
```
Distance (cm) = (pulse_duration_us / 2) / 29.1
```

---

### 5. **LED Matrix Display (MAX7219) - Robust Text Rendering**

**Files Modified:**
- `display/max7219_driver.py` - Complete rewrite with image rotation
- `display/expressions.py` - Face expression animations (unchanged)

**Why:**
- **Text was cut off or upside-down** due to orientation issues
- **LUMA block_orientation** doesn't work well for all setups
- **Need robust rendering** that works regardless of physical mounting

**Solution:**
- **Auto-detects SPI device** (`/dev/spidev0.0`, `/dev/spidev0.1`, `/dev/spidev10.0`)
- **Image rotation pipeline:**
  1. Create horizontal Pillow image with text
  2. Text origin at `(device_width + X_OFFSET, centered vertically)`
  3. Rotate entire image by `ORIENTATION` (0, 90, 180, 270)
  4. Scroll rotated image across display
- **Config-driven:** `cascaded`, `orientation`, `scroll_speed`, `x_offset` from config
- **Always uses `block_orientation=0`** - rotation handled via image rotation

**Config Example:**
```yaml
board_options:
  led_matrix:
    cascaded: 4
    orientation: 180
    scroll_speed: 0.03
    x_offset: 0
```

---

### 6. **Audio System - Fixed Device Configuration**

**Files Modified:**
- `examples/full_hw_test.py` - Fixed mic/speaker devices
- `voice/tts.py` - Fixed speaker device

**Why:**
- **Audio devices were unreliable** - default device detection failed
- **Error 524** from `aplay` - device not accessible
- **Need consistent audio I/O** for voice commands and responses

**Solution:**
- **Fixed microphone:** `plughw:1,0` (USB mic)
- **Fixed speaker:** `plughw:3,0` (USB speaker/amp)
- **Environment variable override:** `AUDIO_PLAYBACK` for speaker device
- **Fallback logic:** Try fixed device, then default, then list available devices
- **Recording duration:** Fixed to 5 seconds for hardware test

**Audio Flow:**
1. Record 5 seconds from `plughw:1,0` → `/tmp/tokymon_test.wav`
2. Play back on `plughw:3,0` (or `$AUDIO_PLAYBACK` if set)
3. Log device used before playback

---

### 7. **Camera Integration - rpicam-still Support**

**Files Modified:**
- `examples/full_hw_test.py` - Camera capture with rotation

**Why:**
- **Raspberry Pi 5 uses `rpicam-still`** instead of `libcamera-still`
- **Camera orientation** - images upside-down need 180° rotation
- **Binary detection** - need to find correct camera command

**Solution:**
- **Priority order:** `rpicam-still` → `libcamera-still` → `raspistill`
- **Auto-detection:** Checks common paths (`/usr/bin/rpicam-still`, etc.)
- **Image rotation:** After capture, rotate 180° using PIL
- **Troubleshooting:** Detailed error messages with fix steps

**Camera Flow:**
1. Try `rpicam-still -o photo.jpg -t 1000`
2. If successful, rotate image 180° with PIL
3. Save to `data/temp/tokymon_photo.jpg`
4. Show on LED display: "PHOTO" + success expression

---

### 8. **Hardware Test Suite - Comprehensive Auto-Test**

**Files Created/Modified:**
- `examples/full_hw_test.py` - Complete hardware test flow
- `scripts/full_hw_test_run.sh` - Test runner script

**Why:**
- **Need automated validation** of all hardware components
- **Troubleshooting guide** for common issues
- **Simulator mode** for development without hardware

**Test Flow:**
1. **LED Matrix** - Show "TOKYMON", expressions, clear
2. **Audio** - Record 5s, play back on fixed devices
3. **Camera** - Capture photo, rotate 180°, display
4. **IR Sensors** - Read left/right obstacle detection
5. **Ultrasonic** - Measure distance (cm)
6. **Motors** - Forward, backward, turn left, turn right, stop
7. **Final Display** - Show "OK" on LED matrix

**Features:**
- **Simulator mode:** Logs actions without hardware access
- **Error handling:** Detailed troubleshooting steps
- **Temp directory:** Auto-detects writable temp location
- **Device detection:** Auto-finds audio/camera devices

---

### 9. **Safety System**

**Files Created:**
- `control/safety.py` - Safety manager with watchdog

**Why:**
- **Prevent runaway motors** - emergency stop if software crashes
- **Policy enforcement** - only allow safe movement commands
- **Heartbeat monitoring** - detect if main loop stops responding

**Features:**
- **Watchdog timer:** Stops motors if heartbeat missed
- **Policy engine:** Whitelist of allowed actions
- **Duration limits:** Max movement time enforced
- **Emergency stop:** Immediate motor shutdown

---

### 10. **Simulator Mode - Development Without Hardware**

**Files Created:**
- `sensors/simulator.py` - Sensor simulators

**Why:**
- **Develop on Mac** without Raspberry Pi hardware
- **Test logic** without physical components
- **CI/CD friendly** - tests run without hardware

**Implementation:**
- **Environment variable:** `TOKY_ENV=dev` enables simulator
- **Config flag:** `use_simulator: true` in `services.yaml`
- **Mock behavior:** All hardware calls log instead of execute
- **Realistic values:** Simulators return plausible sensor readings

**Example:**
```python
if USE_SIM:
    LOGGER.info("show_text(sim): TOKYMON")
    return  # Skip hardware access
```

---

### 11. **MQTT Message Bus**

**Files Created:**
- `system/mqtt_bus.py` - MQTT client with simulator mock

**Why:**
- **Inter-component communication** - sensors → brain → actuators
- **Remote control** - send commands via MQTT
- **Logging/telemetry** - publish sensor data

**Features:**
- **Simulator mode:** Mock MQTT client (logs to console)
- **Production:** Real MQTT broker connection
- **Topic prefix:** `tokymon/` for all topics
- **Auto-reconnect:** Handles connection failures

---

### 12. **Voice Integration (STT/TTS)**

**Files Created:**
- `voice/stt.py` - Speech-to-text (Whisper integration)
- `voice/tts.py` - Text-to-speech (espeak + aplay)
- `voice/audio.py` - Audio I/O utilities

**Why:**
- **Voice commands** - control robot via speech
- **Voice feedback** - robot speaks responses
- **Natural interaction** - more intuitive than buttons

**Implementation:**
- **STT:** Whisper model for speech recognition
- **TTS:** espeak for synthesis, aplay for playback
- **Fixed devices:** Mic `plughw:1,0`, Speaker `plughw:3,0`
- **Simulator:** Logs text instead of audio I/O

---

### 13. **Brain/LLM Integration**

**Files Created:**
- `brain/llm_gateway.py` - LLM API integration
- `brain/intent_parser.py` - Parse user intents
- `brain/policy_engine.py` - Safety policy enforcement
- `brain/state_manager.py` - Robot state tracking

**Why:**
- **Natural language commands** - "move forward", "turn left", etc.
- **Intent understanding** - convert speech to actions
- **Safety first** - policy engine blocks unsafe commands

**Flow:**
1. User speaks → STT converts to text
2. Text → LLM → Intent (move, stop, etc.)
3. Intent → Policy engine → Allowed/Blocked
4. If allowed → Execute action via motors/sensors

---

### 14. **Testing Infrastructure**

**Files Created:**
- `tests/unit/` - Unit tests for individual components
- `tests/integration/` - Integration tests for full flows

**Why:**
- **Verify correctness** - ensure code works as expected
- **Regression prevention** - catch bugs before deployment
- **Documentation** - tests show how to use components

**Test Coverage:**
- Motor driver (TB6612)
- Ultrasonic sensor (HC-SR04)
- MQTT bus (mock and real)
- Hardware flow (simulator mode)

---

### 15. **Deployment Scripts**

**Files Created:**
- `scripts/deploy_to_pi.sh` - Deploy code to Raspberry Pi
- `scripts/run_tokymon.sh` - Main entrypoint
- `scripts/tokymon.service` - Systemd service file
- `scripts/install_requirements.sh` - Install dependencies

**Why:**
- **Automated deployment** - push code to Pi easily
- **Service management** - auto-start on boot
- **Dependency management** - ensure all packages installed

---

## 🎯 Key Design Decisions

### 1. **Config-Driven Architecture**
- **Why:** Easy to change hardware pins, services, behavior without code changes
- **How:** YAML configs + `.env` files for secrets

### 2. **Simulator Mode**
- **Why:** Develop and test on Mac without Raspberry Pi hardware
- **How:** Environment variable `TOKY_ENV=dev` + config flag `use_simulator: true`

### 3. **Hardware Abstraction**
- **Why:** Support different hardware (L298 vs TB6612, different sensors)
- **How:** Driver layer with consistent interfaces

### 4. **Safety First**
- **Why:** Prevent damage to robot or environment
- **How:** Policy engine + watchdog timers + emergency stop

### 5. **Pi 5 Compatibility**
- **Why:** Raspberry Pi 5 has different GPIO architecture
- **How:** Always use `SafeGPIO` (lgpio) + global GPIO offset conversion

---

## 📊 Current Status

### ✅ **Completed:**
- Project structure and configuration system
- GPIO abstraction (Pi 5 compatible)
- Motor driver (TB6612)
- Sensor drivers (IR, Ultrasonic)
- LED matrix display (MAX7219 with image rotation)
- Audio system (fixed devices)
- Camera integration (rpicam-still with rotation)
- Hardware test suite
- Simulator mode
- Safety system
- MQTT bus
- Voice integration (STT/TTS)
- Brain/LLM integration (scaffold)
- Testing infrastructure
- Deployment scripts

### 🔄 **In Progress:**
- Real LLM provider integration (OpenAI API keys)
- Real STT provider integration (Whisper API)
- Real TTS provider integration (ElevenLabs API)

### 📝 **TODO:**
- Validate on actual Raspberry Pi 5 hardware
- Fine-tune sensor calibrations
- Add more expressions/animations
- Implement advanced navigation logic
- Add MQTT topic handlers for remote control

---

## 🚀 How to Use

### **Development (Mac):**
```bash
cd "/Users/ankursharma/Documents/Dev Projects/tokymon"
export TOKY_ENV=dev
python3 main.py
```

### **Hardware Test (Pi):**
```bash
cd /home/ankursharma/Projects/tokymon
export TOKY_ENV=prod
./scripts/full_hw_test_run.sh
```

### **Run Tests:**
```bash
TOKY_ENV=dev PYTHONPATH=. pytest -q
```

---

## 📚 Key Files Reference

| File | Purpose |
|------|---------|
| `main.py` | Main entrypoint |
| `system/config.py` | Configuration loader |
| `control/motors.py` | Motor control (TB6612) |
| `sensors/drivers/hcsr04.py` | Ultrasonic sensor |
| `display/max7219_driver.py` | LED matrix display |
| `examples/full_hw_test.py` | Complete hardware test |
| `voice/tts.py` | Text-to-speech |
| `brain/llm_gateway.py` | LLM integration |

---

## 🔒 Security Notes

- **Never commit secrets** - `.env` files are gitignored
- **API keys** stored in `.env.local` (not in repo)
- **Simulator mode** safe for development (no hardware access)

---

## 📞 Support

For issues or questions:
1. Check `README.md` for setup instructions
2. Run `examples/full_hw_test.py` for hardware diagnostics
3. Check logs in simulator mode for debugging

---

**Last Updated:** 2025-12-04
**Project Status:** ✅ Production-Ready Scaffold


