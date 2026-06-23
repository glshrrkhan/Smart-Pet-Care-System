# hardware/servo_control.py — Smart Pet Care
#
# Servo setup:
#   - Single long blade, effectively two blades (symmetric about axle)
#   - CLOSED position: 0°  (duty 2.5%) — blade blocks food opening
#   - OPEN   position: 90° (duty 7.5%) — blade clears opening, food falls
#
# One "portion" = one full OPEN → CLOSE cycle.
# Multiple portions repeat the cycle with a short pause between each.
# PWM is stopped after dispensing so the servo doesn't jitter/hum at rest.

import time

try:
    import RPi.GPIO as GPIO
    MOCK_MODE = False
except ImportError:
    MOCK_MODE = True
    print("[ServoFeeder] RPi.GPIO not found — running in mock mode.")

from config import (
    SERVO_PIN,
    SERVO_PWM_FREQUENCY,
    SERVO_DUTY_CLOSED,
    SERVO_DUTY_OPEN,
    SERVO_OPEN_HOLD_SEC,
    SERVO_CLOSE_HOLD_SEC,
    SERVO_SETTLE_SEC,
)


class ServoFeeder:
    """
    Controls a single-blade servo (two functional positions: 0° closed, 90° open).

    Usage:
        feeder = ServoFeeder()
        feeder.dispense(portions=2)   # open/close twice
        feeder.cleanup()              # call on app shutdown
    """

    def __init__(self, pin: int = SERVO_PIN):
        self.pin  = pin
        self._pwm = None

        if not MOCK_MODE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            GPIO.setup(self.pin, GPIO.OUT)
            self._pwm = GPIO.PWM(self.pin, SERVO_PWM_FREQUENCY)
            # Start with PWM off (duty 0 = no signal, servo stays where it is)
            self._pwm.start(0)
            # Drive to closed position and then silence the signal
            self._set_angle(SERVO_DUTY_CLOSED)
            time.sleep(SERVO_SETTLE_SEC)
            self._pwm.ChangeDutyCycle(0)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _set_angle(self, duty: float):
        """Apply a duty-cycle value. No-op in mock mode."""
        if not MOCK_MODE and self._pwm:
            self._pwm.ChangeDutyCycle(duty)

    def _open_blade(self):
        """Rotate to 90° — blade clears the food opening."""
        self._set_angle(SERVO_DUTY_OPEN)
        time.sleep(SERVO_OPEN_HOLD_SEC)

    def _close_blade(self):
        """Rotate back to 0° — blade blocks the food opening."""
        self._set_angle(SERVO_DUTY_CLOSED)
        time.sleep(SERVO_CLOSE_HOLD_SEC)

    # ── Public API ────────────────────────────────────────────────────────────

    def dispense(self, portions: int = 1):
        """
        Dispense `portions` portions of food.

        Each portion = one OPEN → CLOSE cycle.
        A short pause between portions prevents mechanical stress.
        PWM signal is silenced after the final close to stop jitter.
        """
        portions = max(1, int(portions))

        if MOCK_MODE:
            print(f"[ServoFeeder MOCK] Dispensing {portions} portion(s) "
                  f"(open={SERVO_OPEN_HOLD_SEC}s, close={SERVO_CLOSE_HOLD_SEC}s each)")
            return

        try:
            for i in range(portions):
                print(f"[ServoFeeder] Portion {i + 1}/{portions} — opening blade")
                self._open_blade()

                print(f"[ServoFeeder] Portion {i + 1}/{portions} — closing blade")
                self._close_blade()

                # Brief pause between portions (skip after the last one)
                if i < portions - 1:
                    time.sleep(0.2)

            # Settle then silence PWM — prevents servo jitter / humming at rest
            time.sleep(SERVO_SETTLE_SEC)
            self._pwm.ChangeDutyCycle(0)
            print("[ServoFeeder] Dispense complete.")

        except Exception as exc:
            # Ensure PWM is silenced even on error
            try:
                self._pwm.ChangeDutyCycle(0)
            except Exception:
                pass
            raise RuntimeError(f"Servo dispense error: {exc}") from exc

    def cleanup(self):
        """Release GPIO resources. Call on app shutdown."""
        if not MOCK_MODE:
            try:
                if self._pwm:
                    self._pwm.ChangeDutyCycle(0)
                    self._pwm.stop()
                GPIO.cleanup(self.pin)
            except Exception as exc:
                print(f"[ServoFeeder] Cleanup error: {exc}")
