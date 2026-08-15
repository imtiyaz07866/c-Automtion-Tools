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

        # Users table (supports Username/Password & Google Sign-In with Admin Approval)
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT,
            email TEXT UNIQUE,
            google_id TEXT UNIQUE,
            avatar_url TEXT,
            is_approved INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        
        # Migrations for existing DB
        for col, col_type in [
            ("email", "TEXT"), ("google_id", "TEXT"), ("avatar_url", "TEXT"),
            ("is_approved", "INTEGER DEFAULT 0"), ("is_admin", "INTEGER DEFAULT 0")
        ]:
            try: c.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")
            except: pass

        # Set Admin role for Imtiyaz accounts (imtiyazxbusiness@gmail.com, imtiyaz@786, imtiyaz1, admin)
        try:
            c.execute("UPDATE users SET is_approved=1, is_admin=1 WHERE LOWER(email) LIKE '%imtiyaz%' OR LOWER(email) LIKE '%imzbusiness%' OR LOWER(username) LIKE '%imtiyaz%' OR LOWER(username)='admin'")
            conn.commit()
        except:
            pass

        # Auto-seed default Super Admin if database is freshly created
        try:
            user_count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            if user_count == 0:
                default_pass_hash = hash_password("imtiyaz123")
                c.execute(
                    "INSERT INTO users (id, username, password_hash, display_name, email, is_approved, is_admin) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (1, "imtiyaz", default_pass_hash, "Imtiyaz Alam", "imtiyazxbusiness@gmail.com", 1, 1)
                )
                c.execute(
                    "INSERT OR REPLACE INTO settings (user_id, key, value) VALUES (?, ?, ?)",
                    (1, "gemini_api_key", "AIzaSyCBF5inRVo777af6Eez7cXAlbmHFWKd9mY")
                )
                conn.commit()
        except:
            pass

        # Channels table (per-user) with target FB pages mapping
        c.execute("""CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            channel_url TEXT NOT NULL,
            channel_name TEXT,
            target_fb_pages TEXT DEFAULT 'all',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            UNIQUE(user_id, channel_url),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
        
        try: c.execute("ALTER TABLE channels ADD COLUMN target_fb_pages TEXT DEFAULT 'all'")
        except: pass

        # Facebook Credentials (per-user) with Backup Token Support
        c.execute("""CREATE TABLE IF NOT EXISTS fb_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            page_id TEXT NOT NULL,
            page_name TEXT,
            access_token TEXT NOT NULL,
            backup_token TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, page_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
        
        try: c.execute("ALTER TABLE fb_credentials ADD COLUMN backup_token TEXT")
        except: pass

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

# ===== User Functions & Private App Mode =====
def is_public_registration_allowed():
    with get_connection() as conn:
        r = conn.cursor().execute("SELECT value FROM settings WHERE key='allow_public_registration'").fetchone()
        return r['value'] == '1' if r else False  # Default PRIVATE MODE (False)

def create_user(username, password, display_name=None, email=None):
    username = username.strip().lower()
    email = (email or "").strip().lower()
    if not username or not password:
        return False, "Username and Password are required.", None
    if len(username) < 3:
        return False, "Username must be at least 3 characters long.", None
    if len(password) < 4:
        return False, "Password must be at least 4 characters long.", None
    
    # Check Private Mode
    with get_connection() as conn:
        user_count = conn.cursor().execute("SELECT COUNT(*) FROM users").fetchone()[0]
        is_imtiyaz = ('imtiyaz' in username or 'imtiyaz' in email or 'imzbusiness' in email or username == 'admin')
        if user_count > 0 and not is_public_registration_allowed() and not is_imtiyaz:
            return False, "🚫 App is currently in Private Mode for Admin Imtiyaz Alam only. Public registrations are closed.", None

    try:
        with get_connection() as conn:
            is_imtiyaz = ('imtiyaz' in username or 'imtiyaz' in email or 'imzbusiness' in email or username == 'admin')
            is_admin = 1 if is_imtiyaz else 0
            is_approved = 1
            
            conn.cursor().execute(
                "INSERT INTO users (username, email, password_hash, display_name, is_approved, is_admin) VALUES (?, ?, ?, ?, ?, ?)",
                (username, email or None, hash_password(password), display_name or username, is_approved, is_admin)
            )
            conn.commit()
            user = conn.cursor().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            set_setting(user['id'], "check_interval_hours", "1")
            set_setting(user['id'], "max_videos_per_sync", "3")
            
            if not is_approved:
                return False, "🔒 Registration Successful! Account is pending approval by Admin Imtiyaz Alam.", None
            return True, "Account registered & approved! You can now log in.", dict(user)
    except sqlite3.IntegrityError:
        return False, "Username or Email is already registered. Please use another.", None
    except Exception as e:
        return False, str(e), None

def login_user(login_input, password):
    login_input = login_input.strip().lower()
    with get_connection() as conn:
        user = conn.cursor().execute(
            "SELECT * FROM users WHERE username=? OR email=?", (login_input, login_input)
        ).fetchone()
        if not user:
            return False, "Invalid email/username or password.", None
        if not verify_password(password, user['password_hash']):
            return False, "Invalid email/username or password.", None
        if not user['is_approved'] and not user['is_admin']:
            return False, "🔒 Access Pending! Your account is awaiting approval by Admin Imtiyaz Alam.", None
        return True, "Login successful!", dict(user)

def get_user_by_id(user_id):
    if not user_id:
        return None
    with get_connection() as conn:
        user = conn.cursor().execute("SELECT id, username, display_name, email, avatar_url, is_approved, is_admin, created_at FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(user) if user else None

def get_or_create_google_user(email, google_id=None, name=None, picture=None):
    email = email.strip().lower()
    name = name or email.split('@')[0]
    with get_connection() as conn:
        cursor = conn.cursor()
        user = cursor.execute(
            "SELECT * FROM users WHERE email=? OR google_id=? OR username=?",
            (email, google_id or "", email)
        ).fetchone()
        
        if user:
            cursor.execute(
                "UPDATE users SET google_id=COALESCE(google_id, ?), avatar_url=COALESCE(avatar_url, ?), display_name=COALESCE(display_name, ?) WHERE id=?",
                (google_id, picture, name, user['id'])
            )
            conn.commit()
            updated = cursor.execute("SELECT * FROM users WHERE id=?", (user['id'],)).fetchone()
            if not updated['is_approved'] and not updated['is_admin']:
                return False, "🔒 Access Pending! Aapka account Admin Imtiyaz Alam ki approval ke liye pending hai.", None
            return True, "Google Sign-In successful!", dict(updated)
            
        user_count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if user_count > 0 and not is_public_registration_allowed() and 'imzbusiness' not in email and 'imtiyaz' not in email:
            return False, "🚫 App is currently in Private Mode for Admin Imtiyaz Alam only. Public registrations are closed.", None

        is_admin = 1 if (user_count == 0 or 'imzbusiness' in email or 'imtiyaz' in email) else 0
        is_approved = 1 if is_admin else 0
        
        dummy_hash = hash_password(secrets.token_hex(16))
        cursor.execute(
            "INSERT INTO users (username, password_hash, display_name, email, google_id, avatar_url, is_approved, is_admin) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (email, dummy_hash, name, email, google_id, picture, is_approved, is_admin)
        )
        conn.commit()
        new_user = cursor.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        set_setting(new_user['id'], "check_interval_hours", "1")
        set_setting(new_user['id'], "max_videos_per_sync", "3")
        
        if not is_approved:
            return False, "🔒 Registration Successful! Account is pending approval by Admin Imtiyaz Alam.", None
            
        return True, "Google account created & logged in!", dict(new_user)

def approve_user(user_id):
    with get_connection() as conn:
        conn.cursor().execute("UPDATE users SET is_approved=1 WHERE id=?", (user_id,))
        conn.commit()

def reject_user(user_id):
    with get_connection() as conn:
        conn.cursor().execute("DELETE FROM users WHERE id=? AND is_admin!=1", (user_id,))
        conn.commit()

def get_all_users():
    with get_connection() as conn:
        return [dict(r) for r in conn.cursor().execute("SELECT id, username, display_name, email, avatar_url, is_approved, is_admin, created_at FROM users ORDER BY id ASC").fetchall()]

def get_user_by_id(user_id):
    with get_connection() as conn:
        user = conn.cursor().execute("SELECT id, username, display_name, created_at FROM users WHERE id=?", (user_id,)).fetchone()
        return dict(user) if user else None

# ===== Channel Functions (per-user) =====
def add_channel(user_id, url, name=None, target_fb_pages="all"):
    url = url.strip()
    if not url:
        return False, "URL khali nahi ho sakta."
    try:
        with get_connection() as conn:
            conn.cursor().execute(
                "INSERT INTO channels (user_id, channel_url, channel_name, target_fb_pages) VALUES (?, ?, ?, ?)",
                (user_id, url, name or url, target_fb_pages or "all")
            )
            conn.commit()
        log_activity(user_id, "INFO", f"Channel added: {url} (Target FB: {target_fb_pages})")
        return True, "Channel add ho gaya!"
    except sqlite3.IntegrityError:
        return False, "Yeh channel pehle se add hai."
    except Exception as e:
        return False, str(e)

def update_channel_target(user_id, cid, target_fb_pages):
    with get_connection() as conn:
        conn.cursor().execute(
            "UPDATE channels SET target_fb_pages=? WHERE id=? AND user_id=?",
            (target_fb_pages or "all", cid, user_id)
        )
        conn.commit()
    log_activity(user_id, "INFO", f"Updated channel {cid} mapping to FB pages: {target_fb_pages}")
    return True

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
def save_fb_credentials(user_id, page_id, token, name=None, backup_token=None):
    try:
        with get_connection() as conn:
            conn.cursor().execute("""INSERT INTO fb_credentials (user_id, page_id, access_token, backup_token, page_name, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id, page_id) DO UPDATE SET 
                access_token = excluded.access_token,
                backup_token = COALESCE(excluded.backup_token, fb_credentials.backup_token),
                page_name = COALESCE(excluded.page_name, fb_credentials.page_name),
                updated_at = CURRENT_TIMESTAMP
            """, (user_id, page_id.strip(), token.strip(), (backup_token or "").strip() or None, name or f"Page-{page_id}"))
            conn.commit()
        log_activity(user_id, "INFO", f"FB credentials saved for Page {page_id}")
        return True, "Facebook credentials saved!"
    except Exception as e:
        return False, str(e)

def update_fb_credentials(user_id, page_id, token=None, name=None, backup_token=None):
    try:
        with get_connection() as conn:
            query = "UPDATE fb_credentials SET updated_at=CURRENT_TIMESTAMP"
            params = []
            if token is not None and token.strip():
                query += ", access_token=?"
                params.append(token.strip())
            if backup_token is not None:
                query += ", backup_token=?"
                params.append(backup_token.strip() or None)
            if name is not None and name.strip():
                query += ", page_name=?"
                params.append(name.strip())
            query += " WHERE user_id=? AND page_id=?"
            params.extend([user_id, page_id.strip()])
            
            conn.cursor().execute(query, params)
            conn.commit()
        log_activity(user_id, "INFO", f"Updated FB Page {page_id}")
        return True, "Facebook Page updated successfully!"
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
def is_video_processed(user_id, vid, pid, title=None):
    with get_connection() as conn:
        # Check by video ID
        row = conn.cursor().execute(
            "SELECT id FROM upload_history WHERE user_id=? AND yt_video_id=? AND fb_page_id=? AND status='success'",
            (user_id, vid, pid)
        ).fetchone()
        if row:
            return True
            
        # Anti-Duplicate Guard: Check by Title similarity
        if title and title.strip():
            clean_title = title.strip().lower()
            rows = conn.cursor().execute(
                "SELECT yt_video_title FROM upload_history WHERE user_id=? AND fb_page_id=? AND status='success'",
                (user_id, pid)
            ).fetchall()
            for r in rows:
                existing = (r['yt_video_title'] or '').strip().lower()
                if existing and len(clean_title) > 5 and (clean_title == existing or clean_title in existing or existing in clean_title):
                    return True
                    
        return False

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

def get_upload_counts(user_id):
    with get_connection() as conn:
        s = conn.cursor().execute("SELECT COUNT(id) FROM upload_history WHERE user_id=? AND status='success'", (user_id,)).fetchone()
        f = conn.cursor().execute("SELECT COUNT(id) FROM upload_history WHERE user_id=? AND status='failed'", (user_id,)).fetchone()
        return (s[0] if s else 0), (f[0] if f else 0)

# ===== Settings (per-user with Global Sharing) =====
def get_setting(user_id, key, default=None):
    with get_connection() as conn:
        r = conn.cursor().execute("SELECT value FROM settings WHERE user_id=? AND key=?", (user_id, key)).fetchone()
        val = r['value'] if r else None
        if (val is None or str(val).strip() == "") and key in ["gemini_api_key", "allow_public_registration"]:
            admin_r = conn.cursor().execute("SELECT value FROM settings WHERE user_id=1 AND key=?", (key,)).fetchone()
            val = admin_r['value'] if admin_r else None
        return val if val is not None else default

def set_setting(user_id, key, val):
    with get_connection() as conn:
        conn.cursor().execute(
            "INSERT INTO settings (user_id, key, value) VALUES (?,?,?) ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value",
            (user_id, key, str(val))
        )
        if key == "gemini_api_key" and str(val).strip() != "":
            # Auto-apply Gemini API key across all accounts
            conn.cursor().execute("UPDATE settings SET value=? WHERE key='gemini_api_key'", (str(val),))
            conn.cursor().execute("""
                INSERT OR IGNORE INTO settings (user_id, key, value)
                SELECT id, 'gemini_api_key', ? FROM users
            """, (str(val),))
        conn.commit()

def request_stop_sync(user_id):
    set_setting(user_id, "stop_requested", "1")
    set_setting(user_id, "active_progress", "🛑 Process Cancelled by User")
    log_activity(user_id, "WARNING", "🛑 Emergency Cancel/Stop triggered by user!")

def is_stop_requested(user_id):
    return get_setting(user_id, "stop_requested", "0") == "1"

def clear_stop_request(user_id):
    set_setting(user_id, "stop_requested", "0")

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

# ===== Admin Management Functions =====
def get_all_users():
    with get_connection() as conn:
        return [dict(r) for r in conn.cursor().execute("SELECT id, username, display_name, email, is_approved, is_admin, created_at FROM users ORDER BY id ASC").fetchall()]

def approve_user(user_id):
    with get_connection() as conn:
        conn.cursor().execute("UPDATE users SET is_approved=1 WHERE id=?", (user_id,))
        conn.commit()

def reject_user(user_id):
    with get_connection() as conn:
        conn.cursor().execute("DELETE FROM users WHERE id=? AND is_admin=0", (user_id,))
        conn.commit()

# Drop old tables and re-init (fresh start with user-based schema)
def reset_db():
    with get_connection() as conn:
        for table in ['activity_logs', 'upload_history', 'settings', 'fb_credentials', 'channels', 'users']:
            conn.cursor().execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
    init_db()

# Initialize (DO NOT use reset_db here - it wipes all user data!)
init_db()
