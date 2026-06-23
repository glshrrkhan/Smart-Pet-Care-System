# main.py
# NOTE: The temperature logger and auto-feeder scheduler now run as
# background threads automatically when you start app.py.
# You no longer need to run main.py separately.
#
# Simply run:
#   python app.py
#
# Both background services start automatically:
#   - Temperature logger (every 5 minutes)
#   - Auto-feeder scheduler (checks every 30 seconds)
#
# This file is kept only for standalone temperature testing.

import sys
import os
import time

root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(root_dir)

from config import TEMP_LOG_INTERVAL
from db.database import init_db, log_temperature
from hardware.temperature_sensor import TemperatureSensor


def run_temperature_logger():
    init_db()
    sensor = TemperatureSensor()
    print("Standalone temperature logger started. Press Ctrl+C to stop.")
    try:
        while True:
            try:
                temp = sensor.read_temperature()
                try:
                    hum = sensor.read_humidity()
                except Exception:
                    hum = None
                log_temperature(temp, hum)
                print(f"Logged: {temp}°C  Humidity: {hum}%")
            except Exception as exc:
                print(f"Read error: {exc}")
            time.sleep(TEMP_LOG_INTERVAL)
    except KeyboardInterrupt:
        print("Stopped.")
        sensor.cleanup()


if __name__ == "__main__":
    run_temperature_logger()
