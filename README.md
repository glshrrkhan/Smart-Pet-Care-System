<img width="1843" height="961" alt="image" src="https://github.com/user-attachments/assets/b2ee083d-5d08-4a2e-ae3a-dec464bbd80b" /><img width="1843" height="961" alt="image" src="https://github.com/user-attachments/assets/511c9d56-a2df-47ca-a793-46e05580cf00" /><img width="1843" height="961" alt="image" src="https://github.com/user-attachments/assets/4cc1caa6-d5c6-44ae-8d9d-35791e8b460b" /><img width="1843" height="961" alt="image" src="https://github.com/user-attachments/assets/d6adc33e-638f-4e3b-9936-a5e46f2ded5e" /><h1 align="center">🐾 Smart Pet Care</h1>

<p align="center">
An IoT-based automated pet feeding and environment monitoring system built with Flask and Raspberry Pi.
</p>

<p align="center">
<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white" />
<img src="https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white" />
<img src="https://img.shields.io/badge/Raspberry_Pi-A22846?style=for-the-badge&logo=raspberry-pi&logoColor=white" />
</p>

---

## 📖 Overview

**Smart Pet Care** is a web-controlled IoT system that automates feeding your pet and monitors its environment. From a single dashboard, an owner can schedule automatic feedings, dispense food manually, watch a live camera feed, and track temperature and humidity over time.

The application is built around a Raspberry Pi with a servo-driven feeder, a DHT22 temperature/humidity sensor, and a CSI camera. To make development and demos easy, **every hardware module automatically falls back to a mock mode** when the physical components (or the Raspberry Pi libraries) aren't available — so the full app runs on any laptop without any hardware attached.

---

## ✨ Features

- **🔐 User authentication** — Secure signup and login with salted SHA-256 password hashing.
- **⏰ Automatic scheduled feeding** — Set multiple feeding times (e.g. `08:00, 13:00, 18:00`); a background scheduler triggers the servo at the right moment and prevents double-feeding within the same minute.
- **🍽 Manual feed-now** — Instantly dispense 1–10 portions on demand.
- **🌡 Temperature & humidity monitoring** — A background thread logs readings every 5 minutes and raises high/low temperature alerts.
- **❄️🔥 Climate controls** — Fan and heater controls surface automatically when temperature crosses the configured thresholds.
- **📷 Live camera stream** — MJPEG video feed of your pet via the Pi camera (placeholder stream in mock mode).
- **🐶 Pet profile** — Store your pet's name, type, breed, and age, with full edit history preserved.
- **📊 Activity logs** — Complete history of feeding events and environmental readings.
- **🥫 Food level tracking** — Food level decreases per portion dispensed, with a low-food warning and a one-click refill reset.
- **🔌 REST status endpoint** — `/api/status` returns live readings as JSON for potential AJAX refresh or integration.

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python, Flask |
| **Database** | SQLite |
| **Frontend** | HTML, Jinja2 templates, CSS |
| **Hardware** | Raspberry Pi, SG90 servo (GPIO PWM), DHT22 sensor, CSI camera |
| **Hardware Libraries** | RPi.GPIO, adafruit_dht / Adafruit_DHT, picamera2 |
| **Concurrency** | Python threading (background scheduler + temperature logger) |

---

## 🏗 Architecture

```
Pet Care Project/
│
├── app.py                      # Flask app: routes, auth, background threads
├── main.py                     # Standalone temperature logger (optional/testing)
├── config.py                   # Central config: GPIO pins, servo timing, thresholds
│
├── db/
│   ├── __init__.py
│   └── database.py             # SQLite schema, auth, logs, settings, migrations
│
├── hardware/
│   ├── __init__.py
│   ├── servo_control.py        # Servo feeder driver (PWM) + mock mode
│   ├── temperature_sensor.py   # DHT22 reader with retry logic + mock mode
│   └── camera.py               # MJPEG camera stream + mock mode
│
└── templates/
    ├── base.html
    ├── login.html
    ├── signup.html
    └── dashboard.html
```

The two background services (temperature logger and auto-feeder scheduler) start automatically as daemon threads when you run `app.py` — there's no need to run anything separately.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- (Optional) Raspberry Pi with servo, DHT22 sensor, and CSI camera for full hardware functionality

### Installation

```bash
# Clone the repository
git clone https://github.com/glshrrkhan/Smart-Pet-Care-System.git
cd Smart-Pet-Care-System

# (Recommended) create a virtual environment
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# Install dependencies
pip install flask

# On a Raspberry Pi, also install the hardware libraries:
# pip install RPi.GPIO adafruit-circuitpython-dht
# sudo apt install -y python3-picamera2 libcamera-apps
```

### Run

```bash
python app.py
```

Then open **http://localhost:5000** in your browser. Create an account on the signup page, log in, and you'll land on the dashboard.

> 💡 **No hardware? No problem.** Without a Raspberry Pi, the servo, sensor, and camera run in mock mode — the servo prints its actions, the sensor returns realistic simulated readings, and the camera serves a placeholder stream. The entire app is fully usable for development and demos.

---

## ⚙️ Configuration

Key settings live in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `SERVO_PIN` | `18` | GPIO pin for the feeder servo |
| `DHT_PIN` | `17` | GPIO pin for the DHT22 sensor |
| `TEMP_LOG_INTERVAL` | `300` | Seconds between temperature readings |
| `TEMP_ALERT_HIGH` | `30.0` | High-temperature alert threshold (°C) |
| `TEMP_ALERT_LOW` | `20.0` | Low-temperature alert threshold (°C) |
| `SCHEDULER_POLL_INTERVAL` | `30` | Seconds between feeding-schedule checks |

> ⚠️ **Security note:** Before any real deployment, change `FLASK_SECRET_KEY` in `config.py` to a strong, unique value.

---

 

## 🔮 Future Improvements

- Live AJAX dashboard refresh using the existing `/api/status` endpoint
- Email/push notifications for temperature alerts and low food
- Multi-pet support
- Charts and graphs for historical temperature trends
- Camera-based feeding detection

---

## 👤 Author

**Gul Sher Khan**
Software Engineering Graduate

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/gul-sher-khan-0119aa264/)
[![Email](https://img.shields.io/badge/Email-D14836?style=for-the-badge&logo=gmail&logoColor=white)](mailto:glshrrkhan@gmail.com)
