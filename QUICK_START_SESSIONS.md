# Quick Start: Running Sessions on Raspberry Pi

## 🚀 Fastest Way to Run

```bash
# 1. SSH into Pi
ssh pi@raspberrypi.local

# 2. Navigate to project
cd /home/ankursharma/Projects/tokymon

# 3. Activate venv and run
source venv/bin/activate
python3 main_session.py
```

## 📋 Setup as Service (One-Time)

```bash
# On Raspberry Pi
cd /home/ankursharma/Projects/tokymon
chmod +x scripts/run_session.sh
sudo cp scripts/tokymon_session.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tokymon_session.service
```

## 🎛️ Control Commands

```bash
# Start
sudo systemctl start tokymon_session.service

# Stop
sudo systemctl stop tokymon_session.service

# Restart
sudo systemctl restart tokymon_session.service

# View logs
tail -f /var/log/tokymon/tokymon_session.log

# Check status
sudo systemctl status tokymon_session.service
```

## ⚙️ Configure Modules

Edit `configs/services.yaml`:

```yaml
sessions:
  max_modules_per_session: 3
  # Uncomment to select specific modules:
  # selected_modules: ["object_identification", "environment_orientation"]
```

## 📊 What Happens

1. **Session Starts**: Orchestrator initializes and selects modules
2. **Modules Run**: Each module executes in sequence (enter → run → exit)
3. **Logging**: All execution logged with timestamps and engagement signals
4. **Session Ends**: Results published to MQTT and logged

## 🔴 Emergency Stop

- Press `Ctrl+C` if running manually
- `sudo systemctl stop tokymon_session.service` if running as service
- Emergency stop works from ANY state

## 📝 Logs Location

- Service logs: `/var/log/tokymon/tokymon_session.log`
- System logs: `sudo journalctl -u tokymon_session.service`

## 🧪 Test First (Mac)

```bash
export TOKY_ENV=dev  # Simulator mode
python3 main_session.py
```

See `SESSION_DEPLOYMENT.md` for full documentation.

