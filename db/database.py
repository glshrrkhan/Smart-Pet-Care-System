import sqlite3
import hashlib
import os
from contextlib import contextmanager
from datetime import datetime
from config import DB_PATH


# ── Connection ────────────────────────────────────────────────────────────────

@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def now_text() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ── Schema helpers ────────────────────────────────────────────────────────────

def _table_exists(conn, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    ).fetchone()
    return row is not None


def _get_table_sql(conn, table_name: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    ).fetchone()
    return row["sql"] if row and row["sql"] else ""


def _create_pet_profile_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS PetProfile (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            pet_name   TEXT NOT NULL DEFAULT 'My Pet',
            pet_type   TEXT NOT NULL DEFAULT 'Dog',
            pet_breed  TEXT NOT NULL DEFAULT '',
            pet_age    TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        )
    """)


def _migrate_pet_profile_if_needed(conn):
    """
    Old database had:
        id INTEGER PRIMARY KEY CHECK (id = 1)

    That allowed only one pet profile forever.
    This migration replaces it with AUTOINCREMENT and keeps old data.
    """
    if not _table_exists(conn, "PetProfile"):
        _create_pet_profile_table(conn)
        return

    table_sql = _get_table_sql(conn, "PetProfile")
    compact_sql = table_sql.lower().replace(" ", "")

    old_single_profile_table = (
        "check(id=1)" in compact_sql
        or "check(id=1)" in compact_sql.replace("=", " = ")
    )

    if not old_single_profile_table:
        return

    backup_name = "PetProfile_old_migration"

    conn.execute("DROP TABLE IF EXISTS PetProfile_old_migration")
    conn.execute("ALTER TABLE PetProfile RENAME TO PetProfile_old_migration")

    _create_pet_profile_table(conn)

    old_rows = conn.execute("""
        SELECT pet_name, pet_type, pet_breed, pet_age, updated_at
        FROM PetProfile_old_migration
        ORDER BY id ASC
    """).fetchall()

    if old_rows:
        for row in old_rows:
            conn.execute("""
                INSERT INTO PetProfile
                    (pet_name, pet_type, pet_breed, pet_age, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                row["pet_name"] or "My Pet",
                row["pet_type"] or "Dog",
                row["pet_breed"] or "",
                row["pet_age"] or "",
                row["updated_at"] or now_text(),
            ))

    conn.execute(f"DROP TABLE IF EXISTS {backup_name}")


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db():
    with get_connection() as conn:
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS Users (
                user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt          TEXT NOT NULL,
                created_at    TEXT NOT NULL
            )
        """)

        _migrate_pet_profile_if_needed(conn)

        c.execute("""
            CREATE TABLE IF NOT EXISTS FeedingLogs (
                log_id       INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp    TEXT NOT NULL,
                action_type  TEXT NOT NULL,
                portion_size INTEGER NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS TemperatureLogs (
                log_id            INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp         TEXT NOT NULL,
                temperature_value REAL NOT NULL,
                humidity_value    REAL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS Settings (
                setting_key   TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL,
                last_updated  TEXT NOT NULL
            )
        """)

        # Performance indexes
        c.execute("CREATE INDEX IF NOT EXISTS idx_feed_ts ON FeedingLogs(timestamp DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_temp_ts ON TemperatureLogs(timestamp DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_pet_updated ON PetProfile(updated_at DESC, id DESC)")

        # Default pet profile row — only insert if table is empty
        count = c.execute("SELECT COUNT(*) FROM PetProfile").fetchone()[0]
        if count == 0:
            c.execute("""
                INSERT INTO PetProfile
                    (pet_name, pet_type, pet_breed, pet_age, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, ("My Pet", "Dog", "", "", now_text()))

        # Default settings
        for key, val in [
            ("feeding_times", "08:00,13:00,18:00"),
            ("portion_size",  "1"),
            ("food_level",    "100"),
        ]:
            c.execute("""
                INSERT OR IGNORE INTO Settings
                    (setting_key, setting_value, last_updated)
                VALUES (?, ?, ?)
            """, (key, val, now_text()))


# ── User auth ─────────────────────────────────────────────────────────────────

def _hash(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


def create_user(username: str, password: str):
    salt = os.urandom(16).hex()
    hashed = _hash(password, salt)

    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO Users
                    (username, password_hash, salt, created_at)
                VALUES (?, ?, ?, ?)
            """, (
                username.strip(),
                hashed,
                salt,
                now_text(),
            ))
        return True, None
    except sqlite3.IntegrityError:
        return False, "Username already exists."


def verify_user(username: str, password: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("""
            SELECT password_hash, salt
            FROM Users
            WHERE username = ?
        """, (username.strip(),)).fetchone()

    if not row:
        return False

    return _hash(password, row["salt"]) == row["password_hash"]


def any_users_exist() -> bool:
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) FROM Users").fetchone()[0] > 0


# ── Pet profile ───────────────────────────────────────────────────────────────

def get_pet_profile() -> dict:
    """
    Return the latest saved pet profile.

    Important:
    Do NOT use WHERE id = 1 here.
    PetProfile is now a history table, so latest row is the active profile.
    """
    with get_connection() as conn:
        row = conn.execute("""
            SELECT *
            FROM PetProfile
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
        """).fetchone()

    return dict(row) if row else {}


def update_pet_profile(pet_name: str, pet_type: str, pet_breed: str, pet_age: str):
    """
    Save a new pet profile row every time.
    This preserves pet profile history instead of overwriting one row.
    """
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO PetProfile
                (pet_name, pet_type, pet_breed, pet_age, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            pet_name.strip() or "My Pet",
            pet_type.strip() or "Dog",
            pet_breed.strip(),
            pet_age.strip(),
            now_text(),
        ))


def get_pet_profile_history(limit: int = None) -> list:
    """
    Return pet profile history, newest first.
    Pass limit=None for all records.
    """
    with get_connection() as conn:
        if limit is None:
            rows = conn.execute("""
                SELECT *
                FROM PetProfile
                ORDER BY updated_at DESC, id DESC
            """).fetchall()
        else:
            rows = conn.execute("""
                SELECT *
                FROM PetProfile
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
            """, (limit,)).fetchall()

    return [dict(r) for r in rows]


# ── Feeding logs ──────────────────────────────────────────────────────────────

def log_feeding(action_type: str, portion_size: int):
    """
    Save feeding log and update food level in one transaction.

    This prevents a bug where food level changes but the feeding log fails,
    or the feeding log saves but food level does not update.
    """
    portion_size = int(portion_size)
    if portion_size < 1:
        raise ValueError("portion_size must be at least 1")

    timestamp = now_text()

    with get_connection() as conn:
        row = conn.execute("""
            SELECT setting_value
            FROM Settings
            WHERE setting_key = ?
        """, ("food_level",)).fetchone()

        try:
            current_level = int(row["setting_value"]) if row else 100
        except ValueError:
            current_level = 100

        new_level = max(0, current_level - (portion_size * 5))

        conn.execute("""
            INSERT INTO FeedingLogs
                (timestamp, action_type, portion_size)
            VALUES (?, ?, ?)
        """, (
            timestamp,
            action_type.strip() or "manual",
            portion_size,
        ))

        conn.execute("""
            INSERT INTO Settings
                (setting_key, setting_value, last_updated)
            VALUES (?, ?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET
                setting_value = excluded.setting_value,
                last_updated  = excluded.last_updated
        """, (
            "food_level",
            str(new_level),
            timestamp,
        ))


def get_recent_feeding_logs(limit: int = None) -> list:
    """
    Return feeding logs, newest first.

    limit=None means return all feeding logs.
    limit=10 means return latest 10 only.
    """
    with get_connection() as conn:
        if limit is None:
            rows = conn.execute("""
                SELECT *
                FROM FeedingLogs
                ORDER BY timestamp DESC, log_id DESC
            """).fetchall()
        else:
            rows = conn.execute("""
                SELECT *
                FROM FeedingLogs
                ORDER BY timestamp DESC, log_id DESC
                LIMIT ?
            """, (limit,)).fetchall()

    return [dict(r) for r in rows]


def get_all_feeding_logs() -> list:
    return get_recent_feeding_logs(limit=None)


def get_feeding_count_today() -> int:
    today = datetime.now().strftime("%Y-%m-%d")

    with get_connection() as conn:
        return conn.execute("""
            SELECT COUNT(*)
            FROM FeedingLogs
            WHERE timestamp LIKE ?
        """, (f"{today}%",)).fetchone()[0]


# ── Temperature logs ──────────────────────────────────────────────────────────

def log_temperature(temp: float, humidity: float = None):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO TemperatureLogs
                (timestamp, temperature_value, humidity_value)
            VALUES (?, ?, ?)
        """, (
            now_text(),
            temp,
            humidity,
        ))


def get_recent_temperature_logs(limit: int = None) -> list:
    """
    Return temperature logs, newest first.

    limit=None means return all temperature logs.
    limit=10 means return latest 10 only.
    """
    with get_connection() as conn:
        if limit is None:
            rows = conn.execute("""
                SELECT *
                FROM TemperatureLogs
                ORDER BY timestamp DESC, log_id DESC
            """).fetchall()
        else:
            rows = conn.execute("""
                SELECT *
                FROM TemperatureLogs
                ORDER BY timestamp DESC, log_id DESC
                LIMIT ?
            """, (limit,)).fetchall()

    return [dict(r) for r in rows]


def get_all_temperature_logs() -> list:
    return get_recent_temperature_logs(limit=None)


# ── Settings ──────────────────────────────────────────────────────────────────

def set_setting(key: str, value: str):
    timestamp = now_text()

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO Settings
                (setting_key, setting_value, last_updated)
            VALUES (?, ?, ?)
            ON CONFLICT(setting_key) DO UPDATE SET
                setting_value = excluded.setting_value,
                last_updated  = excluded.last_updated
        """, (
            key,
            value,
            timestamp,
        ))


def get_setting(key: str, default=None):
    with get_connection() as conn:
        row = conn.execute("""
            SELECT setting_value
            FROM Settings
            WHERE setting_key = ?
        """, (key,)).fetchone()

    return row["setting_value"] if row else default