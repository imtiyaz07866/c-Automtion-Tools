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
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        uid = get_uid()
        user = db.get_user_by_id(uid) if uid else None
        if not user or not user.get('is_admin'):
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({"error": "Admin access required"}), 403
            return redirect(url_for('index'))
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

@app.route("/admin")
@login_required
@admin_required
def admin_page():
    return render_template("admin.html", user=db.get_user_by_id(get_uid()))

@app.route("/")
@login_required
def index():
    return render_template("index.html", user=db.get_user_by_id(get_uid()))

# ===== Auth API =====
@app.route("/api/register", methods=["POST"])
def api_register():
    d = request.json or {}
    ok, msg, user = db.create_user(
        username=d.get("username",""),
        password=d.get("password",""),
        display_name=d.get("display_name"),
        email=d.get("email")
    )
    return jsonify({"success": ok, "message": msg})

@app.route("/api/login", methods=["POST"])
def api_login():
    d = request.json or {}
    login_input = d.get("username") or d.get("email") or ""
    ok, msg, user = db.login_user(login_input, d.get("password",""))
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
    ok, msg = db.save_fb_credentials(get_uid(), d.get("page_id",""), d.get("access_token",""), d.get("page_name"), d.get("backup_token"))
    return jsonify({"success": ok, "message": msg})

@app.route("/api/facebook/exchange-token", methods=["POST"])
@login_required
def api_exchange_fb_token():
    d = request.json or {}
    short_token = d.get("short_lived_token", "").strip()
    app_id = d.get("app_id", "").strip()
    app_secret = d.get("app_secret", "").strip()
    
    if not short_token or not app_id or not app_secret:
        return jsonify({"success": False, "message": "Short-lived token, App ID, and App Secret required!"}), 400
        
    url = "https://graph.facebook.com/v19.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_token
    }
    try:
        import requests
        res = requests.get(url, params=params, timeout=15)
        data = res.json()
        if "access_token" in data:
            return jsonify({
                "success": True, 
                "message": "Long-lived Permanent Token generated!", 
                "long_lived_token": data["access_token"]
            })
        else:
            err = data.get("error", {}).get("message", res.text)
            return jsonify({"success": False, "message": f"Exchange failed: {err}"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500

@app.route("/api/facebook/verify-token", methods=["POST"])
@login_required
def api_verify_fb_token():
    d = request.json or {}
    token = d.get("access_token", "").strip()
    if not token:
        return jsonify({"success": False, "message": "Access token is required!"}), 400
        
    try:
        import requests
        url = "https://graph.facebook.com/v19.0/me"
        params = {"fields": "id,name,permissions", "access_token": token}
        r = requests.get(url, params=params, timeout=10)
        j = r.json()
        
        if r.status_code == 200 and "id" in j:
            name = j.get("name", "Facebook Page")
            pid = j.get("id")
            
            perms_data = j.get("permissions", {}).get("data", [])
            granted = [p["permission"] for p in perms_data if p.get("status") == "granted"]
            
            req_perms = ["pages_manage_posts", "pages_read_engagement"]
            missing = [p for p in req_perms if p not in granted]
            
            if missing and perms_data:
                return jsonify({
                    "success": False,
                    "message": f"Token connected to '{name}' ({pid}), BUT missing permissions: {', '.join(missing)}. Please add 'pages_manage_posts' permission in Graph Explorer!",
                    "page_id": pid,
                    "page_name": name
                })
                
            return jsonify({
                "success": True,
                "message": f"✅ Token Valid! Connected to '{name}' (ID: {pid}). Ready for auto-posting!",
                "page_id": pid,
                "page_name": name
            })
        else:
            err = j.get("error", {}).get("message", r.text)
            return jsonify({"success": False, "message": f"Token Invalid: {err}"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/facebook/fetch-user-pages", methods=["POST"])
@login_required
def api_fetch_user_pages():
    d = request.json or {}
    token = d.get("user_token", "").strip()
    if not token:
        return jsonify({"success": False, "message": "Facebook Token required!"}), 400
        
    try:
        import requests
        url = "https://graph.facebook.com/v19.0/me/accounts"
        params = {
            "fields": "id,name,access_token,category",
            "limit": 100,
            "access_token": token
        }
        r = requests.get(url, params=params, timeout=15)
        j = r.json()
        
        if r.status_code == 200 and "data" in j:
            pages = j["data"]
            if not pages:
                return jsonify({"success": False, "message": "No Facebook Pages found managed by this account!"}), 404
            return jsonify({
                "success": True,
                "message": f"Found {len(pages)} Facebook Page(s)!",
                "pages": pages
            })
        else:
            err = j.get("error", {}).get("message", r.text)
            return jsonify({"success": False, "message": f"Failed to fetch Facebook Pages: {err}"}), 400
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/facebook/connect-multiple-pages", methods=["POST"])
@login_required
def api_connect_multiple_pages():
    d = request.json or {}
    pages = d.get("pages", [])
    if not pages:
        return jsonify({"success": False, "message": "No pages selected!"}), 400
        
    added_count = 0
    uid = get_uid()
    for p in pages:
        pid = str(p.get("id", "")).strip()
        token = str(p.get("access_token", "")).strip()
        name = str(p.get("name", "")).strip()
        if pid and token:
            ok, msg = db.save_fb_credentials(uid, pid, token, name)
            if ok:
                added_count += 1
                
    return jsonify({
        "success": True,
        "message": f"Successfully connected {added_count} Facebook Page(s)!"
    })

@app.route("/api/facebook/<pid>", methods=["PUT"])
@login_required
def api_update_fb(pid):
    d = request.json or {}
    ok, msg = db.update_fb_credentials(
        get_uid(), pid, 
        token=d.get("access_token"), 
        name=d.get("page_name"), 
        backup_token=d.get("backup_token")
    )
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
    success, failed = db.get_upload_counts(uid)
    interval = db.get_setting(uid, "check_interval_hours", "1")
    active_progress = db.get_setting(uid, "active_progress", "")
    return jsonify({
        "active_channels": len([c for c in channels if c.get("is_active")]),
        "total_channels": len(channels),
        "fb_pages": len(fb),
        "total_uploads": success,
        "failed_uploads": failed,
        "interval": interval,
        "active_progress": active_progress
    })

@app.route("/api/progress", methods=["GET"])
@login_required
def api_progress():
    uid = get_uid()
    return jsonify({"active_progress": db.get_setting(uid, "active_progress", "")})

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
        "max_videos_per_sync": db.get_setting(uid, "max_videos_per_sync", "3"),
        "gemini_api_key": db.get_setting(uid, "gemini_api_key", ""),
        "allow_public_registration": db.get_setting(1, "allow_public_registration", "0"),
        "user_info": session.get("user", {})
    })

# ===== Admin User Approval API =====
@app.route("/api/admin/users", methods=["GET"])
@login_required
def api_admin_get_users():
    return jsonify(db.get_all_users())

@app.route("/api/admin/approve-user", methods=["POST"])
@login_required
def api_admin_approve_user():
    target_id = request.json.get("user_id")
    if target_id:
        db.approve_user(target_id)
        return jsonify({"success": True, "message": "User Approved Successfully!"})
    return jsonify({"success": False, "message": "Invalid user ID"}), 400

@app.route("/api/admin/reject-user", methods=["POST"])
@login_required
def api_admin_reject_user():
    target_id = request.json.get("user_id")
    if target_id:
        db.reject_user(target_id)
        return jsonify({"success": True, "message": "User Removed!"})
    return jsonify({"success": False, "message": "Invalid user ID"}), 400

@app.route("/api/settings", methods=["POST"])
@login_required
def api_save_settings():
    uid = get_uid()
    d = request.json or {}
    db.set_setting(uid, "check_interval_hours", d.get("check_interval_hours", "1"))
    db.set_setting(uid, "max_videos_per_sync", d.get("max_videos_per_sync", "3"))
    if "gemini_api_key" in d:
        db.set_setting(uid, "gemini_api_key", d.get("gemini_api_key", ""))
    if "allow_public_registration" in d:
        db.set_setting(uid, "allow_public_registration", str(d.get("allow_public_registration", "0")))
    return jsonify({"success": True, "message": "Settings Saved Successfully!"})

# ===== Manual Post API =====
@app.route("/api/manual-post", methods=["POST"])
@login_required
def api_manual_post():
    uid = get_uid()
    d = request.json or {}
    url = d.get("video_url", "").strip()
    target_fb_pages = d.get("target_fb_pages", "all")
    custom_title = d.get("custom_title")
    custom_desc = d.get("custom_desc")
    
    if not url:
        return jsonify({"success": False, "message": "YouTube Video URL is required!"}), 400
        
    t = threading.Thread(
        target=engine.run_manual_post_for_user, 
        args=(uid, url, target_fb_pages, custom_title, custom_desc), 
        daemon=True
    )
    t.start()
    return jsonify({"success": True, "message": "Manual video upload started in background!"})

# ===== Sync API =====
@app.route("/api/sync", methods=["POST"])
@login_required
def api_sync():
    uid = get_uid()
    t = threading.Thread(target=engine.run_sync_for_user, args=(uid,), daemon=True)
    t.start()
    return jsonify({"success": True, "message": "Sync started!"})

# ===== Cancel / Stop API =====
@app.route("/api/cancel-process", methods=["POST"])
@login_required
def api_cancel_process():
    uid = get_uid()
    db.request_stop_sync(uid)
    return jsonify({"success": True, "message": "🛑 Stopping active process..."})

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
