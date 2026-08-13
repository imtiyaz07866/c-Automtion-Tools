import sqlite3
import os
import hashlib
import secrets
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "automation.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_connection() as conn:
        c = conn.cursor()

        # Users table
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")

        # Channels table (per-user)
        c.execute("""CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            channel_url TEXT NOT NULL,
            channel_name TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            UNIQUE(user_id, channel_url),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")

        # Facebook Credentials (per-user)
        c.execute("""CREATE TABLE IF NOT EXISTS fb_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            page_id TEXT NOT NULL,
            page_name TEXT,
            access_token TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, page_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")

        # Upload History (per-user)
        c.execute("""CREATE TABLE IF NOT EXISTS upload_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            yt_video_id TEXT NOT NULL,
            yt_video_title TEXT,
            channel_url TEXT,
            fb_page_id TEXT,
            fb_post_id TEXT,
            status TEXT NOT NULL,
            error_message TEXT,
            processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, yt_video_id, fb_page_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")

        # Settings (per-user)
        c.execute("""CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (user_id, key),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")

        # Activity Logs (per-user)
        c.execute("""CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            log_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            level TEXT DEFAULT 'INFO',
            message TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")

        conn.commit()

# ===== Password Hashing =====
def hash_password(password):
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"

def verify_password(password, stored_hash):
    try:
        salt, h = stored_hash.split(":")
        return hashlib.sha256((salt + password).encode()).hexdigest() == h
    except:
        return False

# ===== User Functions =====
def create_user(username, password, display_name=None):
    username = username.strip().lower()
    if not username or not password:
        return False, "Username aur Password dono zaroori hain.", None
    if len(username) < 3:
        return False, "Username kam se kam 3 characters ka hona chahiye.", None
    if len(password) < 4:
        return False, "Password kam se kam 4 characters ka hona chahiye.", None
    try:
        with get_connection() as conn:
            conn.cursor().execute(
                "INSERT INTO users (username, password_hash, display_name) VALUES (?, ?, ?)",
                (username, hash_password(password), display_name or username)
            )
            conn.commit()
            user = conn.cursor().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            # Set default settings for new user
            set_setting(user['id'], "check_interval_hours", "1")
            set_setting(user['id'], "max_videos_per_sync", "3")
            return True, "Account ban gaya! Ab login karein.", dict(user)
    except sqlite3.IntegrityError:
        return False, "Yeh username pehle se hai. Doosra try karein.", None
    except Exception as e:
        return False, str(e), None

def login_user(username, password):
    username = username.strip().lower()
    with get_connection() as conn:
        user = conn.cursor().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not user:
            return False, "Username galat hai.", None
        if not verify_password(password, user['password_hash']):
            return False, "Password galat hai.", None
        return True, "Login successful!", dict(user)

def get_user_by_id(user_id):
    with get_connection() as conn:
        user = conn.cursor().execute("SELECT id, username, display_name, created_at FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(user) if user else None

# ===== Channel Functions (per-user) =====
def add_channel(user_id, url, name=None):
    url = url.strip()
    if not url:
        return False, "URL khali nahi ho sakta."
    try:
        with get_connection() as conn:
            conn.cursor().execute(
                "INSERT INTO channels (user_id, channel_url, channel_name) VALUES (?, ?, ?)",
                (user_id, url, name or url)
            )
            conn.commit()
        log_activity(user_id, "INFO", f"Channel added: {url}")
        return True, "Channel add ho gaya!"
    except sqlite3.IntegrityError:
        return False, "Yeh channel pehle se add hai."
    except Exception as e:
        return False, str(e)

def get_channels(user_id):
    with get_connection() as conn:
        return [dict(r) for r in conn.cursor().execute(
            "SELECT * FROM channels WHERE user_id=? ORDER BY added_at DESC", (user_id,)
        ).fetchall()]

def delete_channel(user_id, cid):
    with get_connection() as conn:
        conn.cursor().execute("DELETE FROM channels WHERE id=? AND user_id=?", (cid, user_id))
        conn.commit()

def toggle_channel(user_id, cid, active):
    with get_connection() as conn:
        conn.cursor().execute("UPDATE channels SET is_active=? WHERE id=? AND user_id=?", (active, cid, user_id))
        conn.commit()

# ===== Facebook Credentials (per-user) =====
def save_fb_credentials(user_id, page_id, token, name=None):
    try:
        with get_connection() as conn:
            conn.cursor().execute("""INSERT INTO fb_credentials (user_id, page_id, access_token, page_name, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, page_id) DO UPDATE SET access_token=excluded.access_token,
                page_name=COALESCE(excluded.page_name, fb_credentials.page_name), updated_at=CURRENT_TIMESTAMP
            """, (user_id, page_id.strip(), token.strip(), name or f"Page-{page_id}"))
            conn.commit()
        log_activity(user_id, "INFO", f"FB credentials saved: {page_id}")
        return True, "Facebook page save ho gaya!"
    except Exception as e:
        return False, str(e)

def get_fb_credentials(user_id):
    with get_connection() as conn:
        return [dict(r) for r in conn.cursor().execute(
            "SELECT * FROM fb_credentials WHERE user_id=? ORDER BY updated_at DESC", (user_id,)
        ).fetchall()]

def delete_fb_credential(user_id, pid):
    with get_connection() as conn:
        conn.cursor().execute("DELETE FROM fb_credentials WHERE page_id=? AND user_id=?", (pid, user_id))
        conn.commit()

# ===== Upload History (per-user) =====
def is_video_processed(user_id, vid, pid):
    with get_connection() as conn:
        return conn.cursor().execute(
            "SELECT id FROM upload_history WHERE user_id=? AND yt_video_id=? AND fb_page_id=? AND status='success'",
            (user_id, vid, pid)
        ).fetchone() is not None

def record_upload(user_id, vid, title, ch_url, fb_pid, fb_post_id, status, err=None):
    with get_connection() as conn:
        conn.cursor().execute("""INSERT INTO upload_history (user_id, yt_video_id, yt_video_title, channel_url, fb_page_id, fb_post_id, status, error_message)
            VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(user_id, yt_video_id, fb_page_id) DO UPDATE SET
            status=excluded.status, fb_post_id=excluded.fb_post_id, error_message=excluded.error_message, processed_at=CURRENT_TIMESTAMP
        """, (user_id, vid, title, ch_url, fb_pid, fb_post_id, status, err))
        conn.commit()

def get_upload_history(user_id, limit=50):
    with get_connection() as conn:
        return [dict(r) for r in conn.cursor().execute(
            "SELECT * FROM upload_history WHERE user_id=? ORDER BY processed_at DESC LIMIT ?", (user_id, limit)
        ).fetchall()]

# ===== Settings (per-user) =====
def get_setting(user_id, key, default=None):
    with get_connection() as conn:
        r = conn.cursor().execute("SELECT value FROM settings WHERE user_id=? AND key=?", (user_id, key)).fetchone()
        return r['value'] if r else default

def set_setting(user_id, key, val):
    with get_connection() as conn:
        conn.cursor().execute(
            "INSERT INTO settings (user_id, key, value) VALUES (?,?,?) ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value",
            (user_id, key, str(val))
        )
        conn.commit()

# ===== Activity Logs (per-user) =====
def log_activity(user_id, level, msg):
    try:
        with get_connection() as conn:
            conn.cursor().execute("INSERT INTO activity_logs (user_id, level, message) VALUES (?,?,?)", (user_id, level, msg))
            conn.commit()
    except:
        pass

def get_activity_logs(user_id, limit=100):
    with get_connection() as conn:
        return [dict(r) for r in conn.cursor().execute(
            "SELECT * FROM activity_logs WHERE user_id=? ORDER BY log_time DESC LIMIT ?", (user_id, limit)
        ).fetchall()]

def clear_logs(user_id):
    with get_connection() as conn:
        conn.cursor().execute("DELETE FROM activity_logs WHERE user_id=?", (user_id,))
        conn.commit()

# ===== Get All Active Users (for scheduler) =====
def get_all_active_user_ids():
    with get_connection() as conn:
        rows = conn.cursor().execute("SELECT DISTINCT user_id FROM channels WHERE is_active=1").fetchall()
        return [r['user_id'] for r in rows]

# Drop old tables and re-init (fresh start with user-based schema)
def reset_db():
    with get_connection() as conn:
        for table in ['activity_logs', 'upload_history', 'settings', 'fb_credentials', 'channels', 'users']:
            conn.cursor().execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
    init_db()

# Initialize (DO NOT use reset_db here - it wipes all user data!)
init_db()
