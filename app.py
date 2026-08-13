import os
import secrets
import threading
from datetime import timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import database as db
import uploader_engine as engine

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("SECRET_KEY", "yt-fb-autoposter-default-secret-key-change-in-production")
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

engine.start_scheduler()

# ===== Auth Decorator =====
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({"error": "Not logged in", "redirect": "/login"}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

def get_uid():
    return session.get('user_id')

# ===== Pages =====
@app.route("/login")
def login_page():
    if 'user_id' in session:
        return redirect("/")
    return render_template("login.html")

@app.route("/")
@login_required
def index():
    return render_template("index.html", user=db.get_user_by_id(get_uid()))

# ===== Auth API =====
@app.route("/api/register", methods=["POST"])
def api_register():
    d = request.json
    ok, msg, user = db.create_user(d.get("username",""), d.get("password",""), d.get("display_name"))
    return jsonify({"success": ok, "message": msg})

@app.route("/api/login", methods=["POST"])
def api_login():
    d = request.json
    ok, msg, user = db.login_user(d.get("username",""), d.get("password",""))
    if ok and user:
        session.permanent = True
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['display_name'] = user.get('display_name', user['username'])
    return jsonify({"success": ok, "message": msg})

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/me", methods=["GET"])
@login_required
def api_me():
    user = db.get_user_by_id(get_uid())
    return jsonify(user)

# ===== Channels API =====
@app.route("/api/channels", methods=["GET"])
@login_required
def api_get_channels():
    return jsonify(db.get_channels(get_uid()))

@app.route("/api/channels", methods=["POST"])
@login_required
def api_add_channel():
    d = request.json
    ok, msg = db.add_channel(get_uid(), d.get("url",""), d.get("name"), d.get("target_fb_pages", "all"))
    return jsonify({"success": ok, "message": msg})

@app.route("/api/channels/<int:cid>/target", methods=["PUT"])
@login_required
def api_update_channel_target(cid):
    d = request.json
    db.update_channel_target(get_uid(), cid, d.get("target_fb_pages", "all"))
    return jsonify({"success": True, "message": "Target FB Pages updated!"})

@app.route("/api/channels/<int:cid>", methods=["DELETE"])
@login_required
def api_del_channel(cid):
    db.delete_channel(get_uid(), cid)
    return jsonify({"success": True})

@app.route("/api/channels/<int:cid>/toggle", methods=["POST"])
@login_required
def api_toggle_channel(cid):
    d = request.json
    db.toggle_channel(get_uid(), cid, d.get("active", 1))
    return jsonify({"success": True})

# ===== Facebook API =====
@app.route("/api/facebook", methods=["GET"])
@login_required
def api_get_fb():
    creds = db.get_fb_credentials(get_uid())
    for c in creds:
        t = c.get("access_token", "")
        c["token_preview"] = f"{t[:12]}...{t[-8:]}" if len(t) > 20 else "***"
    return jsonify(creds)

@app.route("/api/facebook", methods=["POST"])
@login_required
def api_add_fb():
    d = request.json
    ok, msg = db.save_fb_credentials(get_uid(), d.get("page_id",""), d.get("access_token",""), d.get("page_name"))
    return jsonify({"success": ok, "message": msg})

@app.route("/api/facebook/<pid>", methods=["DELETE"])
@login_required
def api_del_fb(pid):
    db.delete_fb_credential(get_uid(), pid)
    return jsonify({"success": True})

# ===== Stats API =====
@app.route("/api/stats", methods=["GET"])
@login_required
def api_stats():
    uid = get_uid()
    channels = db.get_channels(uid)
    fb = db.get_fb_credentials(uid)
    history = db.get_upload_history(uid, 500)
    interval = db.get_setting(uid, "check_interval_hours", "1")
    return jsonify({
        "active_channels": len([c for c in channels if c.get("is_active")]),
        "total_channels": len(channels),
        "fb_pages": len(fb),
        "total_uploads": len([h for h in history if h["status"] == "success"]),
        "failed_uploads": len([h for h in history if h["status"] == "failed"]),
        "interval": interval
    })

# ===== History API =====
@app.route("/api/history", methods=["GET"])
@login_required
def api_history():
    return jsonify(db.get_upload_history(get_uid(), 100))

# ===== Logs API =====
@app.route("/api/logs", methods=["GET"])
@login_required
def api_logs():
    return jsonify(db.get_activity_logs(get_uid(), 100))

@app.route("/api/logs", methods=["DELETE"])
@login_required
def api_clear_logs():
    db.clear_logs(get_uid())
    return jsonify({"success": True})

# ===== Settings API =====
@app.route("/api/settings", methods=["GET"])
@login_required
def api_get_settings():
    uid = get_uid()
    return jsonify({
        "check_interval_hours": db.get_setting(uid, "check_interval_hours", "1"),
        "max_videos_per_sync": db.get_setting(uid, "max_videos_per_sync", "3")
    })

@app.route("/api/settings", methods=["POST"])
@login_required
def api_save_settings():
    uid = get_uid()
    d = request.json
    db.set_setting(uid, "check_interval_hours", d.get("check_interval_hours", "1"))
    db.set_setting(uid, "max_videos_per_sync", d.get("max_videos_per_sync", "3"))
    return jsonify({"success": True, "message": "Settings saved!"})

# ===== Sync API =====
@app.route("/api/sync", methods=["POST"])
@login_required
def api_sync():
    uid = get_uid()
    t = threading.Thread(target=engine.run_sync_for_user, args=(uid,), daemon=True)
    t.start()
    return jsonify({"success": True, "message": "Sync started!"})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
