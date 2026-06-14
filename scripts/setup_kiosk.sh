#!/usr/bin/env bash
# setup_kiosk.sh — one-time setup on Raspberry Pi 5 (Bookworm / Wayland / labwc)
#
# What this script does:
#   1. Installs the tokymon-face systemd service (face server auto-starts at boot)
#   2. Adds Chromium kiosk entry to labwc autostart
#   3. Disables screen blanking / power save on the Pi touchscreen
#
# Run once on the Pi:
#   cd /home/ankursharma/Projects/tokymon
#   bash scripts/setup_kiosk.sh
#
# After running: reboot the Pi.  The face will appear on the touchscreen
# automatically on every subsequent boot — no manual steps needed.

set -euo pipefail

PROJECT_DIR="/home/ankursharma/Projects/tokymon"
SERVICE_SRC="$PROJECT_DIR/configs/tokymon-face.service"
SERVICE_DEST="/etc/systemd/system/tokymon-face.service"
LABWC_DIR="$HOME/.config/labwc"
AUTOSTART="$LABWC_DIR/autostart"

echo "=== Tokymon kiosk setup ==="

# ── 1. systemd face service ───────────────────────────────────────────────────
echo "[1/3] Installing tokymon-face.service …"
sudo cp "$SERVICE_SRC" "$SERVICE_DEST"
sudo systemctl daemon-reload
sudo systemctl enable tokymon-face.service
echo "      Done — tokymon-face will start at boot."

# ── 2. labwc autostart (Chromium kiosk) ──────────────────────────────────────
echo "[2/3] Adding Chromium kiosk to labwc autostart …"
mkdir -p "$LABWC_DIR"

# Guard: only add if not already present
if grep -q "tokymon-kiosk" "$AUTOSTART" 2>/dev/null; then
    echo "      Already present in $AUTOSTART — skipping."
else
    cat >> "$AUTOSTART" <<'KIOSK'

# ── Tokymon face kiosk ──────────────────────────────────────────────────────
# Wait until the face server is ready, then open Chromium fullscreen.
(
  for i in $(seq 1 30); do
    if curl -sf http://localhost:8080/ >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  chromium-browser \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-restore-session-state \
    --disable-features=Translate \
    --check-for-update-interval=31536000 \
    --autoplay-policy=no-user-gesture-required \
    --window-size=800,480 \
    http://localhost:8080/
) &
KIOSK
    echo "      Added to $AUTOSTART."
fi

# ── 3. Disable screen blanking ────────────────────────────────────────────────
echo "[3/3] Disabling screen blanking / DPMS …"
WAYFIRE_CFG="$HOME/.config/wayfire.ini"   # used on some Pi Bookworm builds
if [ -f "$WAYFIRE_CFG" ]; then
    if ! grep -q "idle_inhibit" "$WAYFIRE_CFG"; then
        cat >> "$WAYFIRE_CFG" <<'INI'

[idle]
toggle = <super>z
screensaver_timeout = 0
dpms_timeout = 0
INI
        echo "      Added idle config to wayfire.ini."
    else
        echo "      Idle config already present in wayfire.ini — skipping."
    fi
else
    echo "      wayfire.ini not found — add screen blanking disable manually if needed."
fi

echo ""
echo "=== Setup complete ==="
echo "    Reboot the Pi to activate:"
echo "    sudo reboot"
