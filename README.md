# Tokymon POC

Tokymon is a Raspberry Pi 5 robot scaffold with configurable sensors, simulator-friendly drivers, and a safety-first control stack.

## Canonical Paths

- **Mac dev root:** `/Users/ankursharma/Documents/Dev Projects/tokymon`
- **Raspberry Pi root:** `/home/ankursharma/Projects/tokymon`

Use these exact paths throughout scripts, docs, and deployment steps.

## Local Dev (Mac)

```bash
cd "/Users/ankursharma/Documents/Dev Projects/tokymon"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install paho-mqtt  # already in requirements, reinstall if missing

cp .env .env.local   # add API keys in .env.local (never commit!)
export TOKY_ENV=dev  # loads configs/env.dev.yaml (simulator on)
python3 main.py
```

### MQTT in Simulator Mode

- The dev simulator uses an internal mock MQTT client, so publishing/subscribing logs to the console. No broker needed.
- To test topics locally:
  ```bash
  TOKY_ENV=dev PYTHONPATH=. python3 - <<'PY'
  from system.mqtt_bus import MqttBus
  bus = MqttBus()
  bus.start()
  bus.publish("tokymon/test", "hello")
  bus.stop()
  PY
  ```

### Running Tests

Always run pytest with the simulator environment and project root on `PYTHONPATH`:

```bash
TOKY_ENV=dev PYTHONPATH=. pytest -q
```

### Hardware Test Flow (Pi)

```bash
ssh pi@raspberrypi.local
cd /home/ankursharma/Projects/tokymon
./scripts/hw_test_run.sh --auto-confirm   # requires venv + systemd deps
```

This runs `examples/hw_test.py`, which performs the full motor/sensor/audio/vision validation with SafetyManager supervision. In non-prod environments, pass `--run-hw` to execute the simulator-only flow.

## Deploy on Raspberry Pi

1. Sync the repo to `/home/ankursharma/Projects/tokymon` (see `scripts/deploy_to_pi.sh`).
2. Create/update `.env` with production secrets.
3. Follow the Pi command checklist in this README (also printed by Cursor).

Systemd install:

```bash
sudo cp scripts/tokymon.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tokymon.service
```

## Repository Highlights

- `configs/` – pin map, services, env overrides (YAML)
- `system/config.py` – loads YAML + `.env`, exposes global `CONFIG`, and injects runtime paths
- `drivers/`, `sensors/` – hardware drivers with simulator fallbacks
- `control/` – motor primitives, safety watchdogs, emergency stop
- `brain/` – LLM gateway, intent parser, policy engine enforcing safe actions
- `scripts/` – setup/deploy helpers plus systemd unit
- `tests/` – unit + integration tests (simulator powered)

## Safety Notes

- Policy engine whitelists `move` actions and clamps durations.
- Safety manager watchdog stops motors if heartbeats are missed.
- Simulator mode routes GPIO/SPI through no-op mocks.

## TODOs

- Implement real LLM/STT/TTS provider calls using secrets from `.env`.
- Flesh out MQTT topics/handlers and display/voice behaviors.
- Validate hardware on the actual Pi once wiring is complete.

## Never Commit Secrets

`.env`, `.env.local`, API keys, and voice tokens must stay in gitignored files only.
