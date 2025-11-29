#!/usr/bin/env python3
"""
Tokymon – RC Car (Bluetooth + Keyboard) ALL-IN-ONE

What this script does automatically:
  • Ensures bluetoothd runs in Classic mode (-C) so SPP works
  • Registers Serial Port Profile (SPP) and makes the Pi discoverable/pairable
  • Uses headless pairing agent (NoInputNoOutput) so no GUI is needed
  • Listens on RFCOMM channel 1 and decodes app inputs (F/B/L/R/S etc.)
  • Also accepts keyboard (arrows or F/B/L/R/S, +/- speed, Q quit)
"""

import os, sys, subprocess, shutil, threading, termios, tty, time
from pathlib import Path

# =========================
# ---- Bluetooth Setup ----
# =========================
BLE_EXEC_CANDIDATES = [
    "/usr/libexec/bluetooth/bluetoothd",  # RPi OS Bookworm/Trixie
    "/usr/lib/bluetooth/bluetoothd",      # Some Debian/Ubuntu
]
OVR_DIR  = Path("/etc/systemd/system/bluetooth.service.d")
OVR_FILE = OVR_DIR / "override.conf"

def need_root():
    if os.geteuid() != 0:
        sys.exit("Please run with sudo: sudo python3 tokymon_dual_control.py")

def run_ok(cmd, **kw):
    try:
        return subprocess.run(cmd, check=True, text=True, **kw)
    except subprocess.CalledProcessError as e:
        print(f"(bt-setup) non-fatal: {e}")
        return e

def bluetoothd_path():
    for p in BLE_EXEC_CANDIDATES:
        if Path(p).exists(): return p
    return None

def ensure_classic_mode():
    """Make bluetoothd run with -C (Classic). Persist via systemd override if needed."""
    bt = bluetoothd_path()
    if not bt:
        print("⚠️ Could not find bluetoothd binary; continuing anyway.")
        return
    # If not already running with -C, create override and restart service
    ps = subprocess.run(["bash","-lc","ps aux | grep '[b]luetoothd -C'"], text=True)
    if ps.returncode == 0:
        return  # already classic

    print("🔧 Enabling Classic mode (-C) for bluetoothd…")
    OVR_DIR.mkdir(parents=True, exist_ok=True)
    OVR_FILE.write_text("[Service]\nExecStart=\nExecStart=%s -C\n" % bt)
    run_ok(["systemctl", "daemon-reexec"])
    run_ok(["systemctl", "daemon-reload"])
    run_ok(["systemctl", "restart", "bluetooth"])
    time.sleep(0.4)

def register_spp_and_expose():
    """Register SPP and make device discoverable/pairable with headless agent."""
    print("🔧 Registering SPP & exposing as discoverable/pairable…")
    run_ok(["rfkill","unblock","bluetooth"])
    run_ok(["systemctl","restart","bluetooth"])
    # SPP
    run_ok(["sdptool","add","SP"])
    # Headless agent + discoverable/pairable
    bt_cfg = (
        "power on\n"
        "agent NoInputNoOutput\n"
        "default-agent\n"
        "pairable on\n"
        "discoverable on\n"
        "discoverable-timeout 0\n"
        "exit\n"
    )
    run_ok(["bluetoothctl"], input=bt_cfg)

def bluetooth_prepare_all():
    tools = ["bluetoothctl","sdptool","rfkill","systemctl"]
    missing = [t for t in tools if not shutil.which(t)]
    if missing:
        print(f"⚠️ Missing tools: {missing}. Bluetooth prep may be limited.")
    ensure_classic_mode()
    register_spp_and_expose()

# ======================
# ---- Motor Control ----
# ======================
from gpiozero import PWMOutputDevice, DigitalOutputDevice

# Preferred pins (left/right enables on 12/13); fall back to 18/19 if busy
PREF_ENA, PREF_ENB = 12, 13   # may clash with onboard PWM audio
FALLBACK_ENA, FALLBACK_ENB = 18, 19

IN1, IN2 = 5, 6               # left dir
IN3, IN4 = 20, 21             # right dir

def mk_pwm(pin):
    return PWMOutputDevice(pin, frequency=1000)

def safe_pwm_pair():
    try:
        ena = mk_pwm(PREF_ENA)
        enb = mk_pwm(PREF_ENB)
        print(f"✅ Using PWM ENA/ENB on BCM {PREF_ENA}/{PREF_ENB}")
        return ena, enb
    except Exception as e:
        print(f"⚠️ PWM pins {PREF_ENA}/{PREF_ENB} busy ({e}). Falling back to {FALLBACK_ENA}/{FALLBACK_ENB}…")
        ena = mk_pwm(FALLBACK_ENA)
        enb = mk_pwm(FALLBACK_ENB)
        print(f"✅ Using PWM ENA/ENB on BCM {FALLBACK_ENA}/{FALLBACK_ENB}")
        return ena, enb

ENA_DEV, ENB_DEV = safe_pwm_pair()
IN1_DEV, IN2_DEV = DigitalOutputDevice(IN1), DigitalOutputDevice(IN2)
IN3_DEV, IN4_DEV = DigitalOutputDevice(IN3), DigitalOutputDevice(IN4)

speed = 0.5
running = True
lock = threading.Lock()

def move(l, r):
    with lock:
        IN1_DEV.value, IN2_DEV.value = (1,0) if l >= 0 else (0,1)
        IN3_DEV.value, IN4_DEV.value = (1,0) if r >= 0 else (0,1)
        ENA_DEV.value, ENB_DEV.value = abs(l), abs(r)

def halt():
    with lock:
        ENA_DEV.value = ENB_DEV.value = 0
        IN1_DEV.off(); IN2_DEV.off(); IN3_DEV.off(); IN4_DEV.off()

def forward(): print("→ FORWARD"); move(speed,  speed)
def back():    print("→ BACK");    move(-speed, -speed)
def left():    print("→ LEFT");    move(-speed,  speed)
def right():   print("→ RIGHT");   move(speed,  -speed)

def faster():
    global speed; speed = min(1.0, speed+0.1); print(f"Speed {speed:.1f}")
def slower():
    global speed; speed = max(0.2, speed-0.1); print(f"Speed {speed:.1f}")
def quit_all():
    global running; running = False; halt()

# ==========================
# ---- Command Decoder  ----
# ==========================
def decode_and_exec(raw: bytes):
    s = raw.decode(errors="ignore").strip()   # b'F\r\n' -> 'F'
    if not s: return
    c = s[0].upper()
    print(f"RX: {raw!r} -> {c}")
    if   c in ('F','U','W','8'): forward()
    elif c in ('B','D','X','2'): back()
    elif c in ('L','A','4'):     left()
    elif c in ('R','6'):         right()
    elif c in ('S','5','0'):     halt()
    elif c == '+':               faster()
    elif c == '-':               slower()
    elif c == 'Q':               quit_all()

# ============================
# ---- Bluetooth Listener  ----
# ============================
def bluetooth_thread():
    try:
        from bluetooth import BluetoothSocket, RFCOMM
    except Exception as e:
        sys.exit(f"PyBluez not installed: {e}\nInstall with: sudo apt install python3-bluez")

    # Ensure BT is ready before opening the socket
    bluetooth_prepare_all()

    server = BluetoothSocket(RFCOMM)
    server.bind(("", 1))          # fixed RFCOMM channel 1
    server.listen(1)
    print("📡 Bluetooth server on RFCOMM channel 1 (SPP)")
    client, info = server.accept()
    print(f"✅ Connected via Bluetooth: {info}")
    client.settimeout(0.1)

    try:
        while running:
            try:
                data = client.recv(64)
                if data:
                    decode_and_exec(data)
            except OSError:
                pass
    finally:
        try: client.close()
        except: pass
        server.close()
        halt()
        print("🛑 BT closed")

# ==========================
# ---- Keyboard Control  ----
# ==========================
def keyboard_thread():
    def read_key():
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            c1 = sys.stdin.read(1)
            if c1 == '\x1b' and sys.stdin.read(1) == '[':  # arrows
                c3 = sys.stdin.read(1)
                return '\x1b[' + c3
            return c1
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    print("🎮 Keyboard: arrows or F/B/L/R/S, +/- speed, Q quit")
    while running:
        k = read_key()
        if   k in ('f','F') or k == '\x1b[A': forward()
        elif k in ('b','B') or k == '\x1b[B': back()
        elif k in ('l','L') or k == '\x1b[D': left()
        elif k in ('r','R') or k == '\x1b[C': right()
        elif k in ('s','S'): halt()
        elif k == '+':       faster()
        elif k == '-':       slower()
        elif k in ('q','Q'): quit_all()

# ==============
# ---- Main ----
# ==============
if __name__ == "__main__":
    need_root()
    try:
        t = threading.Thread(target=bluetooth_thread, daemon=True)
        t.start()
        keyboard_thread()
    except KeyboardInterrupt:
        pass
    finally:
        quit_all()
        print("✅ Tokymon stopped.")