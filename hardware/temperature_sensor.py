import random
import time
from config import DHT_PIN, DHT_SENSOR_TYPE

# Try new CircuitPython lib (Pi OS Bullseye+)
try:
    import board
    import adafruit_dht
    DHT_MODE = "circuitpython"
except ImportError:
    # Fall back to legacy lib
    try:
        import Adafruit_DHT
        DHT_MODE = "legacy"
    except ImportError:
        DHT_MODE = "mock"

# How many times to retry a failed read before giving up
_READ_RETRIES = 5
_RETRY_DELAY  = 0.5   # seconds between retries


class TemperatureSensor:
    def __init__(self, pin=DHT_PIN, sensor_type=DHT_SENSOR_TYPE):
        self.pin = pin
        self.sensor_type = sensor_type.upper()
        self._device = None

        if DHT_MODE == "circuitpython":
            self._init_device()
        elif DHT_MODE == "legacy":
            self._legacy_sensor = (
                Adafruit_DHT.DHT11 if self.sensor_type == "DHT11"
                else Adafruit_DHT.DHT22
            )

    # ── CircuitPython device init / reinit ────────────────────────────────────

    def _init_device(self):
        """Create (or recreate) the adafruit_dht device object."""
        if self._device is not None:
            try:
                self._device.exit()   # release GPIO before reinit
            except Exception:
                pass
        board_pin = getattr(board, f"D{self.pin}")
        cls = (adafruit_dht.DHT11 if self.sensor_type == "DHT11"
               else adafruit_dht.DHT22)
        # use_pulseio=False avoids the PulseIO / GPIO 4 timing conflict
        # that causes "DHT sensor not found" on certain Pi OS versions
        self._device = cls(board_pin, use_pulseio=False)

    def _read_with_retry(self) -> tuple:
        """
        Return (temperature, humidity) retrying up to _READ_RETRIES times.
        On repeated failure the device is reinitialised before next attempt,
        which clears any stuck GPIO state.
        """
        last_err = None
        for attempt in range(_READ_RETRIES):
            try:
                t = self._device.temperature
                h = self._device.humidity
                if t is None or h is None:
                    raise RuntimeError("Sensor returned None")
                return round(float(t), 2), round(float(h), 2)
            except Exception as exc:
                last_err = exc
                print(f"[DHT22] Read attempt {attempt + 1}/{_READ_RETRIES} failed: {exc}")
                time.sleep(_RETRY_DELAY)
                try:
                    self._init_device()
                except Exception as reinit_err:
                    print(f"[DHT22] Reinit failed: {reinit_err}")
        raise RuntimeError(f"DHT22 failed after {_READ_RETRIES} attempts: {last_err}")

    # ── Public API ────────────────────────────────────────────────────────────

    def read_temperature(self) -> float:
        if DHT_MODE == "circuitpython":
            t, _ = self._read_with_retry()
            return t
        elif DHT_MODE == "legacy":
            _, t = Adafruit_DHT.read_retry(self._legacy_sensor, self.pin)
            if t is None:
                raise RuntimeError("DHT sensor returned None")
            return round(float(t), 2)
        else:
            return round(random.uniform(22.0, 30.0), 2)

    def read_humidity(self) -> float:
        if DHT_MODE == "circuitpython":
            _, h = self._read_with_retry()
            return h
        elif DHT_MODE == "legacy":
            h, _ = Adafruit_DHT.read_retry(self._legacy_sensor, self.pin)
            if h is None:
                raise RuntimeError("DHT humidity returned None")
            return round(float(h), 2)
        else:
            return round(random.uniform(40.0, 65.0), 2)

    def cleanup(self):
        if DHT_MODE == "circuitpython" and self._device:
            try:
                self._device.exit()
            except Exception:
                pass
        self._device = None
