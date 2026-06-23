# app.py — Smart Pet Care
# Includes: auth, dashboard, pet profile, manual feed,
#           schedule update, background auto-feeder, background temp logger

import sys
import os
import threading
import time
import re
from datetime import datetime

root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(root_dir)

from flask import (Flask, render_template, request,
                   redirect, url_for, session, flash, jsonify, Response)
from config import (FLASK_SECRET_KEY, PROJECT_NAME,
                    SCHEDULER_POLL_INTERVAL, TEMP_LOG_INTERVAL,
                    TEMP_ALERT_HIGH, TEMP_ALERT_LOW)
from db.database import (
    init_db,
    get_setting, set_setting,
    get_recent_feeding_logs, get_recent_temperature_logs,
    get_feeding_count_today,
    log_feeding, log_temperature,
    create_user, verify_user, any_users_exist,
    get_pet_profile, update_pet_profile,
)
from hardware.servo_control import ServoFeeder
from hardware.temperature_sensor import TemperatureSensor
from hardware.camera import PetCamera

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

# Hardware — initialised lazily so app starts even without Pi hardware
feeder = ServoFeeder()
sensor = TemperatureSensor()
camera = PetCamera(width=640, height=480, framerate=24)

# ── Temperature cache — keeps last known good reading ─────────────────────────
_temp_cache = {"temp": None, "hum": None, "status": None}
_temp_lock  = threading.Lock()


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_logged_in() -> bool:
    return session.get("logged_in", False)


def valid_time_format(t: str) -> bool:
    """Check HH:MM format."""
    return bool(re.match(r"^\d{2}:\d{2}$", t.strip()))


# ── Background: Temperature Logger ───────────────────────────────────────────

def temperature_logger():
    """Runs in background thread — logs temp + humidity every TEMP_LOG_INTERVAL seconds."""
    print("[BG] Temperature logger started.")
    while True:
        try:
            temp = sensor.read_temperature()
            try:
                hum = sensor.read_humidity()
            except Exception:
                hum = None

            # Determine status
            if temp > TEMP_ALERT_HIGH:
                status = "high"
            elif temp < TEMP_ALERT_LOW:
                status = "low"
            else:
                status = "ok"

            # Update cache with latest good reading
            with _temp_lock:
                _temp_cache["temp"]   = temp
                _temp_cache["hum"]    = hum
                _temp_cache["status"] = status

            log_temperature(temp, hum)

            if status != "ok":
                print(f"[TEMP ALERT] {'HIGH' if status == 'high' else 'LOW'} TEMP: {temp}°C")

        except Exception as exc:
            print(f"[BG] Temperature read error: {exc}")
        time.sleep(TEMP_LOG_INTERVAL)


# ── Background: Auto Feeder Scheduler ────────────────────────────────────────

def auto_feeder_scheduler():
    """Runs in background thread — checks every SCHEDULER_POLL_INTERVAL seconds
    whether a scheduled feeding time has arrived and triggers the servo."""
    print("[BG] Auto-feeder scheduler started.")
    last_fed_minute = None   # prevent double-firing in the same minute

    while True:
        try:
            now_str   = datetime.now().strftime("%H:%M")
            now_minute = datetime.now().strftime("%Y-%m-%d %H:%M")

            times_raw = get_setting("feeding_times", "08:00,13:00,18:00")
            times = [t.strip() for t in times_raw.split(",") if valid_time_format(t.strip())]

            if now_str in times and last_fed_minute != now_minute:
                portions = int(get_setting("portion_size", "1"))
                print(f"[SCHEDULER] Scheduled feeding at {now_str} — {portions} portion(s)")
                feeder.dispense(portions=portions)
                log_feeding("scheduled", portions)
                last_fed_minute = now_minute

        except Exception as exc:
            print(f"[BG] Scheduler error: {exc}")

        time.sleep(SCHEDULER_POLL_INTERVAL)


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if is_logged_in():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if verify_user(username, password):
            session["logged_in"] = True
            session["username"]   = username
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html", project_name=PROJECT_NAME)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if is_logged_in():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm  = request.form.get("confirm_password", "").strip()

        if not username or not password:
            flash("Username and password are required.", "error")
        elif len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        elif password != confirm:
            flash("Passwords do not match.", "error")
        else:
            ok, err = create_user(username, password)
            if ok:
                flash("Account created! Please log in.", "success")
                return redirect(url_for("login"))
            flash(err, "error")
    return render_template("signup.html", project_name=PROJECT_NAME)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def dashboard():
    if not is_logged_in():
        return redirect(url_for("login"))

    feeding_times    = get_setting("feeding_times", "08:00,13:00,18:00")
    portion_size     = get_setting("portion_size", "1")
    food_level       = int(get_setting("food_level", "100"))
    feeding_logs     = get_recent_feeding_logs(limit=10)
    temperature_logs = get_recent_temperature_logs(limit=10)
    feedings_today   = get_feeding_count_today()
    pet              = get_pet_profile()

    # Never read sensor directly here — only background thread reads the sensor
    # This prevents two simultaneous reads which cause DHT22 failures
    with _temp_lock:
        current_temp = _temp_cache["temp"]
        current_hum  = _temp_cache["hum"]
        temp_status  = _temp_cache["status"] or "unavailable"

    return render_template(
        "dashboard.html",
        project_name=PROJECT_NAME,
        username=session.get("username", "User"),
        pet=pet,
        feeding_times=feeding_times,
        portion_size=portion_size,
        food_level=food_level,
        current_temp=current_temp,
        current_hum=current_hum,
        temp_status=temp_status,
        feeding_logs=feeding_logs,
        temperature_logs=temperature_logs,
        feedings_today=feedings_today,
    )


# ── Manual feed ───────────────────────────────────────────────────────────────

@app.route("/feed-now", methods=["POST"])
def feed_now():
    if not is_logged_in():
        return redirect(url_for("login"))
    try:
        portions = int(request.form.get("portions", 1))
        if portions < 1 or portions > 10:
            raise ValueError("Portions must be 1–10")
        feeder.dispense(portions=portions)
        log_feeding("manual", portions)
        flash(f"✅ Fed {portions} portion(s) successfully!", "success")
    except Exception as exc:
        flash(f"❌ Feeding failed: {exc}", "error")
    return redirect(url_for("dashboard"))


# ── Update schedule ───────────────────────────────────────────────────────────

@app.route("/update-schedule", methods=["POST"])
def update_schedule():
    if not is_logged_in():
        return redirect(url_for("login"))

    raw      = request.form.get("feeding_times", "").strip()
    portions = request.form.get("portion_size", "1").strip()

    # Validate each time entry
    times = [t.strip() for t in raw.split(",")]
    invalid = [t for t in times if not valid_time_format(t)]
    if invalid:
        flash(f"❌ Invalid time format: {', '.join(invalid)}. Use HH:MM (e.g. 08:00)", "error")
        return redirect(url_for("dashboard"))

    try:
        p = int(portions)
        if p < 1 or p > 10:
            raise ValueError
    except ValueError:
        flash("❌ Portion size must be a number between 1 and 10.", "error")
        return redirect(url_for("dashboard"))

    set_setting("feeding_times", raw)
    set_setting("portion_size",  str(p))
    flash("✅ Feeding schedule updated!", "success")
    return redirect(url_for("dashboard"))


# ── Pet profile ───────────────────────────────────────────────────────────────

@app.route("/update-pet", methods=["POST"])
def update_pet():
    if not is_logged_in():
        return redirect(url_for("login"))
    update_pet_profile(
        pet_name  = request.form.get("pet_name",  "My Pet").strip(),
        pet_type  = request.form.get("pet_type",  "Dog").strip(),
        pet_breed = request.form.get("pet_breed", "").strip(),
        pet_age   = request.form.get("pet_age",   "").strip(),
    )
    flash("✅ Pet profile updated!", "success")
    return redirect(url_for("dashboard"))


# ── Refill food ───────────────────────────────────────────────────────────────

@app.route("/refill-food", methods=["POST"])
def refill_food():
    if not is_logged_in():
        return redirect(url_for("login"))
    set_setting("food_level", "100")
    flash("✅ Food level reset to 100%!", "success")
    return redirect(url_for("dashboard"))


# ── API: live status (for potential AJAX refresh) ─────────────────────────────

@app.route("/api/status")
def api_status():
    if not is_logged_in():
        return jsonify({"error": "Unauthorized"}), 401
    with _temp_lock:
        temp = _temp_cache["temp"]
        hum  = _temp_cache["hum"]
    return jsonify({
        "temperature": temp,
        "humidity":    hum,
        "food_level":  int(get_setting("food_level", "100")),
        "feedings_today": get_feeding_count_today(),
        "timestamp":   datetime.now().isoformat(timespec="seconds"),
    })


# ── Camera stream ─────────────────────────────────────────────────────────────

@app.route("/video-feed")
def video_feed():
    """MJPEG stream — embedded directly in dashboard via <img> tag."""
    if not is_logged_in():
        return "", 403
    return Response(
        camera.generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()

    # Start background threads (daemon=True so they stop when Flask stops)
    threading.Thread(target=temperature_logger,    daemon=True, name="TempLogger").start()
    threading.Thread(target=auto_feeder_scheduler, daemon=True, name="Scheduler").start()

    # Start camera
    try:
        camera.start()
    except Exception as e:
        print(f"[Camera] Could not start: {e} — dashboard will show offline message.")

    print(f"🐾 {PROJECT_NAME} starting on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)