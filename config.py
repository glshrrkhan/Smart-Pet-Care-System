from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH  = BASE_DIR / "petcare.db"

# ── Project identity ──────────────────────────────────────────────
PROJECT_NAME = "Smart Pet Care"

# ── GPIO / Hardware ───────────────────────────────────────────────
SERVO_PIN    = 18
DHT_PIN      = 17              # Changed from GPIO 4 — GPIO 4 has timing conflicts with adafruit_dht
DHT_SENSOR_TYPE = "DHT22"      # "DHT11" or "DHT22"

# ── Feeding / Servo ───────────────────────────────────────────────
# Servo has a single long blade — two positions: closed (0°) and open (90°)
# At 50 Hz: duty cycle 0° = 2.5%, 90° = 7.5%
SERVO_PWM_FREQUENCY   = 50
SERVO_DUTY_CLOSED     = 2.5    # 0°  — blade closed / resting position
SERVO_DUTY_OPEN       = 7.5    # 90° — blade open, food falls through
SERVO_OPEN_HOLD_SEC   = 0.6    # seconds to hold blade open per portion
SERVO_CLOSE_HOLD_SEC  = 0.4    # seconds to hold blade closed between portions
SERVO_SETTLE_SEC      = 0.3    # seconds after final close before PWM stops
SCHEDULER_POLL_INTERVAL = 30   # seconds — how often to check feeding schedule

# ── Temperature logging ───────────────────────────────────────────
TEMP_LOG_INTERVAL = 300        # seconds (5 minutes)
TEMP_ALERT_HIGH   = 30.0       # °C — alert if above this → turn on fan
TEMP_ALERT_LOW    = 20.0       # °C — alert if below this → turn on heater

# ── Flask ─────────────────────────────────────────────────────────
FLASK_SECRET_KEY = "spc-change-this-in-production-2025"
