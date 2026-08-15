import os, glob, requests, yt_dlp
from apscheduler.schedulers.background import BackgroundScheduler
import database as db

TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_downloads")
os.makedirs(TEMP_DIR, exist_ok=True)

scheduler = None

def cleanup():
    for f in glob.glob(os.path.join(TEMP_DIR, "*")):
        try: os.remove(f)
        except: pass

# Cookie file path: read from env var (Render Secret Files), then /etc/secrets, then local fallback.
# NEVER commit cookies.txt to git — upload via Render Dashboard -> Environment -> Secret Files.
_COOKIES_CANDIDATES = [
    os.environ.get('COOKIES_FILE_PATH', ''),
    '/etc/secrets/cookies.txt',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt'),
]
COOKIES_FILE = next((p for p in _COOKIES_CANDIDATES if p and os.path.exists(p)), '')
COOKIES_CLEAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp_downloads', 'cookies_clean.txt')

def get_cookies_file():
    """Return path to a sanitized (LF-only) cookies.txt for yt-dlp on Linux.

    Reads from COOKIES_FILE_PATH env var (Render Secret Files), falling back to
    /etc/secrets/cookies.txt and finally a local cookies.txt.  The file is
    NEVER read from git — see docs/troubleshooting.md.
    """
    src = next((p for p in _COOKIES_CANDIDATES if p and os.path.exists(p) and os.path.getsize(p) > 5), None)
    if not src:
        return None
    try:
        with open(src, 'r', encoding='utf-8-sig') as f:
            raw = f.read()
        # Normalise line endings to LF (Windows cookies break yt-dlp on Linux)
        clean = raw.replace('\r\n', '\n').replace('\r', '\n')
        if not clean.startswith('# Netscape HTTP Cookie File') and not clean.startswith('# HTTP Cookie File'):
            clean = '# Netscape HTTP Cookie File\n# This is a generated file!\n\n' + clean
        os.makedirs(os.path.dirname(COOKIES_CLEAN), exist_ok=True)
        with open(COOKIES_CLEAN, 'w', encoding='utf-8', newline='\n') as f:
            f.write(clean)
        return COOKIES_CLEAN
    except Exception:
        return src

def fetch_latest_videos(channel_url, max_results=3):
    opts = {
        'extract_flat': 'in_playlist',
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'playlistend': max_results,
        'user_agent': 'com.google.android.youtube/19.29.37 (Linux; U; Android 11; en_US) gzip',
        'extractor_args': {'youtube': {'player_client': ['android', 'mweb']}}
    }
    cookie_path = get_cookies_file()
    if cookie_path:
        opts['cookiefile'] = cookie_path
    videos = []
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
            if 'entries' in info and info['entries']:
                for e in info['entries']:
                    if not e: continue
                    vid = e.get('id')
                    if vid:
                        videos.append({'id': vid, 'title': e.get('title', vid), 'url': e.get('url') or f"https://www.youtube.com/watch?v={vid}"})
            elif 'id' in info:
                videos.append({'id': info['id'], 'title': info.get('title', info['id']), 'url': info.get('webpage_url', f"https://www.youtube.com/watch?v={info['id']}")})
    except Exception as e:
        pass
    return videos

def get_ffmpeg_path():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except:
        return None

def make_progress_hook(user_id):
    last_pct = [-1.0]
    def hook(d):
        if user_id and db.is_stop_requested(user_id):
            raise Exception("Process cancelled by user")
        if d.get('status') == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            if total > 0:
                pct = round((downloaded / total) * 100, 1)
                if abs(pct - last_pct[0]) >= 1.5:
                    last_pct[0] = pct
                    mb_down = round(downloaded / (1024 * 1024), 1)
                    mb_tot = round(total / (1024 * 1024), 1)
                    msg = f"⬇️ Downloading: {pct}% ({mb_down}MB / {mb_tot}MB)"
                    db.set_setting(user_id, "active_progress", msg)
        elif d.get('status') == 'finished':
            db.set_setting(user_id, "active_progress", "⚙️ Merging 4K Ultra HD Streams...")
    return hook

def download_video(video_url, video_id, max_res="4k", user_id=None):
    out = os.path.join(TEMP_DIR, f"{video_id}.%(ext)s")
    ff_path = get_ffmpeg_path()
    cookie_path = get_cookies_file()

    # Diagnostic log with cookie peek
    if user_id:
        try: ver_str = yt_dlp.version.__version__
        except: ver_str = 'unknown'
        ck_info = "NO_FILE"
        if cookie_path and os.path.exists(cookie_path):
            sz = os.path.getsize(cookie_path)
            try:
                with open(cookie_path, 'r', encoding='utf-8') as _f:
                    first_line = _f.readline().strip()
                ck_info = f"YES({sz}B) header={first_line[:30]}"
            except:
                ck_info = f"YES({sz}B)"
        db.log_activity(user_id, "INFO", f"DL start: ytdlp={ver_str} cookies={ck_info} ff={'YES' if ff_path else 'NO'}")

    def find_file():
        for ext in ['mp4', 'mkv', 'webm', 'avi', 'm4v']:
            p = os.path.join(TEMP_DIR, f"{video_id}.{ext}")
            if os.path.exists(p): return p
        matches = glob.glob(os.path.join(TEMP_DIR, f"{video_id}.*"))
        return matches[0] if matches else None

    def make_opts(fmt, clients, cookies=True, ua=None, player_params=None):
        ext_args = {'player_client': clients}
        if player_params:
            ext_args['player_params'] = [player_params]
        o = {
            'format': fmt,
            'outtmpl': out,
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'geo_bypass': True,
            'extractor_args': {'youtube': ext_args},
            # Slow down requests to avoid rate-based bot detection
            'sleep_interval': 3,
            'max_sleep_interval': 8,
            # Retry transient failures before giving up
            'retries': 3,
            'fragment_retries': 3,
        }
        if ua: o['user_agent'] = ua
        if cookies and cookie_path: o['cookiefile'] = cookie_path
        if ff_path:
            o['ffmpeg_location'] = ff_path
            o['merge_output_format'] = 'mp4'
        if user_id:
            o['progress_hooks'] = [make_progress_hook(user_id)]
            db.set_setting(user_id, "active_progress", "Downloading: 0%...")
        return o

    def try_dl(name, fmt, clients, cookies=True, ua=None, player_params=None):
        try:
            with yt_dlp.YoutubeDL(make_opts(fmt, clients, cookies, ua, player_params)) as ydl:
                info = ydl.extract_info(video_url, download=True)
                f = find_file()
                if not f:
                    fn = ydl.prepare_filename(info)
                    base = os.path.splitext(fn)[0]
                    for ext in ['mp4', 'mkv', 'webm']:
                        if os.path.exists(f"{base}.{ext}"):
                            f = f"{base}.{ext}"; break
                if f:
                    if user_id: db.log_activity(user_id, "INFO", f"SUCCESS {name}: {os.path.basename(f)}")
                    return True, f, info.get('title', ''), info.get('description', '')
        except Exception as e:
            err_str = str(e)
            if user_id:
                # Detect YouTube bot-detection specifically for actionable guidance
                if any(kw in err_str for kw in ('Sign in to confirm', 'not a bot', 'bot detection', 'confirm your age')):
                    db.log_activity(user_id, "WARNING",
                        f"{name}: YouTube bot-detection triggered — cookies may be expired or IP flagged. "
                        f"See docs/troubleshooting.md to re-export cookies and upload to Render Secret Files.")
                else:
                    db.log_activity(user_id, "WARNING", f"{name} FAIL: {err_str[:250]}")
        return None

    # Format strings
    if max_res == "720p":
        fmt_hq = 'bestvideo[height<=720]+bestaudio/best[height<=720]/best'
    elif max_res == "1080p":
        fmt_hq = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best'
    else:
        fmt_hq = 'bestvideo+bestaudio/best'
    fmt_safe = '22/18/best'   # itag 22=720p mp4, 18=360p mp4 — always available

    # T1: web client + fresh cookies (standard login session, best format access)
    r = try_dl("T1[web+cookies+HQ]", fmt_hq, ['web'], cookies=True)
    if r: return r

    # T2: web + cookies + safe format
    r = try_dl("T2[web+cookies+safe]", fmt_safe, ['web'], cookies=True)
    if r: return r

    # T3: web_creator (YouTube Studio API) + HQ
    r = try_dl("T3[web_creator+HQ]", fmt_hq, ['web_creator'], cookies=True)
    if r: return r

    # T4: tv_embedded + player_params=IA8= (embed bypass param) + cookies
    r = try_dl("T4[tv_embed+IA8+ck]", fmt_safe, ['tv_embedded'],
               cookies=True, player_params='IA8=')
    if r: return r

    # T5: tv_embedded + IA8= embed bypass, NO cookies (clean session)
    r = try_dl("T5[tv_embed+IA8+clean]", fmt_safe, ['tv_embedded'],
               cookies=False, player_params='IA8=')
    if r: return r

    # T6: android_vr (Daydream - minimal bot checks)
    r = try_dl("T6[android_vr]", fmt_hq, ['android_vr', 'tv_embedded'], cookies=True)
    if r: return r

    # T7: android app UA
    r = try_dl("T7[android]", fmt_hq, ['android'],
               cookies=True, ua='com.google.android.youtube/19.29.37 (Linux; U; Android 11; en_US) gzip')
    if r: return r

    # T8: mweb last resort
    r = try_dl("T8[mweb]", fmt_safe, ['mweb'], cookies=True)
    if r: return r

    if user_id:
        db.log_activity(user_id, "ERROR", "ALL 8 TIERS FAILED. Render IP blocked by YouTube. Check cookie file.")
    return False, "YouTube blocked all download methods on this server IP", "", ""


def upload_to_fb_resumable(file_path, title, desc, page_id, token, user_id=None):
    """Uploads large/long 4K videos using Facebook Graph API Resumable Upload protocol."""
    try:
        file_size = os.path.getsize(file_path)
        url_base = f"https://graph-video.facebook.com/v19.0/{page_id}/videos"
        
        # 1. PHASE START
        start_payload = {
            'upload_phase': 'start',
            'file_size': file_size,
            'access_token': token
        }
        r = requests.post(url_base, data=start_payload, timeout=60)
        j = r.json()
        if r.status_code != 200 or 'upload_session_id' not in j:
            # Fallback to /me/videos endpoint
            url_base = "https://graph-video.facebook.com/v19.0/me/videos"
            r = requests.post(url_base, data=start_payload, timeout=60)
            j = r.json()
            if r.status_code != 200 or 'upload_session_id' not in j:
                err = j.get('error', {}).get('message', r.text)
                return False, None, f"Upload Start Failed: {err}"

        session_id = j['upload_session_id']
        start_offset = int(j.get('start_offset', 0))
        end_offset = int(j.get('end_offset', file_size))
        
        # 2. PHASE TRANSFER (Chunked 8MB transfers)
        with open(file_path, 'rb') as f:
            while start_offset < file_size:
                if user_id and db.is_stop_requested(user_id):
                    return False, None, "Upload cancelled by user"
                f.seek(start_offset)
                chunk = f.read(end_offset - start_offset)
                
                transfer_payload = {
                    'upload_phase': 'transfer',
                    'upload_session_id': session_id,
                    'start_offset': start_offset,
                    'access_token': token
                }
                
                tr = requests.post(
                    url_base, 
                    data=transfer_payload, 
                    files={'video_file_chunk': chunk}, 
                    timeout=300
                )
                tj = tr.json()
                
                if tr.status_code != 200 or 'start_offset' not in tj:
                    terr = tj.get('error', {}).get('message', tr.text)
                    return False, None, f"Chunk Transfer Failed: {terr}"
                    
                start_offset = int(tj['start_offset'])
                end_offset = int(tj.get('end_offset', file_size))
                
                if user_id and file_size > 0:
                    pct = round((start_offset / file_size) * 100, 1)
                    mb_up = round(start_offset / (1024 * 1024), 1)
                    mb_tot = round(file_size / (1024 * 1024), 1)
                    db.set_setting(user_id, "active_progress", f"⬆️ Uploading to FB: {pct}% ({mb_up}MB / {mb_tot}MB)")

        # 3. PHASE FINISH
        finish_payload = {
            'upload_phase': 'finish',
            'upload_session_id': session_id,
            'title': (title or "Video")[:255],
            'description': f"{title}\n\n{(desc or '')[:400]}",
            'access_token': token
        }
        fr = requests.post(url_base, data=finish_payload, timeout=60)
        fj = fr.json()
        if fr.status_code == 200 and (fj.get('success') or 'id' in fj):
            video_id = fj.get('id', session_id)
            if user_id:
                db.set_setting(user_id, "active_progress", "✅ 100% Complete! Video Uploaded!")
            return True, video_id, None
        else:
            ferr = fj.get('error', {}).get('message', fr.text)
            return False, None, f"Upload Finish Failed: {ferr}"

    except Exception as e:
        return False, None, str(e)

def upload_to_fb(file_path, title, desc, page_id, token, user_id=None):
    # Try Resumable Chunked Upload first for large/long 4K videos
    ok, vid, err = upload_to_fb_resumable(file_path, title, desc, page_id, token, user_id)
    if ok:
        return True, vid, None
        
    # Fallback to single-POST upload if resumable returns unsupported error
    endpoints = [
        f"https://graph-video.facebook.com/v19.0/{page_id}/videos",
        "https://graph-video.facebook.com/v19.0/me/videos"
    ]
    payload = {'title': (title or "Video")[:255], 'description': f"{title}\n\n{(desc or '')[:400]}", 'access_token': token}
    
    for url in endpoints:
        try:
            with open(file_path, 'rb') as f:
                r = requests.post(url, data=payload, files={'source': f}, timeout=600)
            if r.status_code == 200:
                j = r.json()
                if 'id' in j:
                    if user_id:
                        db.set_setting(user_id, "active_progress", "✅ 100% Complete! Video Uploaded!")
                    return True, j['id'], None
        except Exception:
            pass
            
    return False, None, err

def generate_gemini_title_and_desc(user_id, title, desc):
    """Uses Google Gemini Free API to generate viral, engaging title & description for FB."""
    api_key = db.get_setting(user_id, "gemini_api_key", "").strip()
    if not api_key:
        return title, desc
        
    models_to_try = [
        "gemini-3.7-flash-video-understanding-eap",
        "gemini-2.5-flash",
        "gemini-flash-latest",
        "gemini-1.5-flash",
        "gemini-2.0-flash"
    ]
    
    prompt = f"""You are a professional social media viral content creator. 
Rewrite the following YouTube video title and description to be extremely engaging, catchy, and optimized for Facebook Reels / Video post with emojis and 5 trending hashtags.

Original Title: {title}
Original Description: {desc[:300] if desc else ''}

IMPORTANT: Reply strictly in JSON format as follows with no markdown codeblocks:
{{"viral_title": "Short Catchy Viral Title with Emojis", "viral_description": "Engaging post description with emojis and #hashtags"}}"""

    headers = {'Content-Type': 'application/json'}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    
    for model in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            r = requests.post(url, json=payload, headers=headers, timeout=12)
            if r.status_code == 200:
                j = r.json()
                raw_text = j['candidates'][0]['content']['parts'][0]['text']
                import json, re
                clean_json = re.sub(r'```json\s*|\s*```', '', raw_text).strip()
                parsed = json.loads(clean_json)
                ai_title = parsed.get('viral_title', title)
                ai_desc = parsed.get('viral_description', desc)
                db.log_activity(user_id, "INFO", f"🤖 Gemini AI generated viral title: '{ai_title}'")
                return ai_title, ai_desc
        except Exception as e:
            continue
            
    return title, desc

def run_sync_for_user(user_id):
    """Run sync for a specific user."""
    db.clear_stop_request(user_id)
    db.log_activity(user_id, "INFO", "Sync started...")
    channels = [c for c in db.get_channels(user_id) if c.get('is_active', 1)]
    fb_creds = db.get_fb_credentials(user_id)
    if not channels:
        db.log_activity(user_id, "WARNING", "No active channels."); return
    if not fb_creds:
        db.log_activity(user_id, "WARNING", "No FB credentials."); return
    mx = int(db.get_setting(user_id, "max_videos_per_sync", "3"))
    total = 0
    for ch in channels:
        if db.is_stop_requested(user_id):
            db.log_activity(user_id, "WARNING", "Sync cancelled by user.")
            break
        db.log_activity(user_id, "INFO", f"Checking: {ch['channel_url']}")
        target_pages = ch.get('target_fb_pages', 'all') or 'all'
        target_ids = [p.strip() for p in target_pages.split(',')] if target_pages != 'all' else None

        for vid in fetch_latest_videos(ch['channel_url'], mx):
            if db.is_stop_requested(user_id):
                db.log_activity(user_id, "WARNING", "Sync cancelled by user.")
                break
            for fb in fb_creds:
                if target_ids and fb['page_id'] not in target_ids:
                    continue
                # Anti-Duplicate Security Guard (ID & Title Check)
                if db.is_video_processed(user_id, vid['id'], fb['page_id'], vid['title']):
                    db.log_activity(user_id, "INFO", f"⚠️ Anti-Duplicate Guard: Skipped already posted video '{vid['title']}' on FB Page {fb['page_id']}")
                    continue

                db.log_activity(user_id, "INFO", f"New video: '{vid['title']}' -> FB {fb['page_id']}")
                ok, path, title, desc = download_video(vid['url'], vid['id'], user_id=user_id)
                if not ok:
                    db.record_upload(user_id, vid['id'], vid['title'], ch['channel_url'], fb['page_id'], None, 'failed', path)
                    db.log_activity(user_id, "ERROR", f"Download failed: {path}")
                    db.set_setting(user_id, "active_progress", "")
                    continue
                    
                # Gemini AI Smart Viral Title & Description Generator
                final_title, final_desc = generate_gemini_title_and_desc(user_id, title or vid['title'], desc)

                uok, pid, uerr = upload_to_fb(path, final_title, final_desc, fb['page_id'], fb['access_token'], user_id=user_id)
                if not uok and fb.get('backup_token'):
                    db.log_activity(user_id, "WARNING", f"Primary token failed for FB Page {fb['page_id']}. Trying Backup Token...")
                    uok, pid, uerr = upload_to_fb(path, final_title, final_desc, fb['page_id'], fb['backup_token'], user_id=user_id)
                    if uok:
                        db.log_activity(user_id, "INFO", f"Backup Token succeeded! Video ID: {pid}")

                db.record_upload(user_id, vid['id'], final_title, ch['channel_url'], fb['page_id'], pid, 'success' if uok else 'failed', uerr)
                if uok:
                    total += 1
                    db.log_activity(user_id, "INFO", f"Posted! FB Video ID: {pid}")
                else:
                    db.log_activity(user_id, "ERROR", f"FB upload failed on primary & backup: {uerr}")
                try: os.remove(path)
                except: pass
    db.log_activity(user_id, "INFO", f"Sync done. Posted: {total}")
    db.set_setting(user_id, "active_progress", f"✅ Sync done. Posted {total} video(s)")

import secrets

def run_manual_post_for_user(user_id, video_url, target_fb_pages="all", custom_title=None, custom_desc=None):
    """Manually post a specific video or latest video from channel to target FB pages."""
    db.clear_stop_request(user_id)
    db.log_activity(user_id, "INFO", f"Manual post process started for link: {video_url}")
    fb_creds = db.get_fb_credentials(user_id)
    if not fb_creds:
        db.log_activity(user_id, "WARNING", "No Facebook Page connected for manual upload.")
        db.set_setting(user_id, "active_progress", "")
        return
        
    target_ids = [p.strip() for p in target_fb_pages.split(',')] if target_fb_pages != 'all' else None
    
    # Auto-resolve channel links to their latest video URL
    actual_url = video_url
    if any(k in video_url.lower() for k in ['/@', '/channel/', '/c/', '/user/']) and not any(k in video_url.lower() for k in ['watch?', '/shorts/', '/v/']):
        db.log_activity(user_id, "INFO", f"Detected channel link. Fetching latest video from: {video_url}")
        vids = fetch_latest_videos(video_url, 1)
        if vids:
            actual_url = vids[0]['url']
            db.log_activity(user_id, "INFO", f"Found latest video: '{vids[0]['title']}' ({actual_url})")
        else:
            db.log_activity(user_id, "ERROR", f"Could not find any videos in channel: {video_url}")
            db.set_setting(user_id, "active_progress", "")
            return
            
    vid = "manual_" + secrets.token_hex(6)
    ok, path, yt_title, yt_desc = download_video(actual_url, vid, user_id=user_id)
    if not ok:
        db.log_activity(user_id, "ERROR", f"Manual video download failed: {path}")
        db.set_setting(user_id, "active_progress", "")
        return
        
    raw_title = (custom_title or yt_title or "Video Post").strip()
    raw_desc = (custom_desc or yt_desc or "").strip()
    
    # Gemini AI Smart Viral Title Generator
    final_title, final_desc = generate_gemini_title_and_desc(user_id, raw_title, raw_desc)
    
    posted_count = 0
    for fb in fb_creds:
        if target_ids and fb['page_id'] not in target_ids:
            continue
            
        # Anti-Duplicate Security Guard (Title Check)
        if db.is_video_processed(user_id, vid, fb['page_id'], yt_title):
            db.log_activity(user_id, "WARNING", f"⚠️ Anti-Duplicate Guard: Video '{yt_title}' was already posted to FB Page {fb['page_id']}. Skipped!")
            continue
            
        uok, pid, uerr = upload_to_fb(path, final_title, final_desc, fb['page_id'], fb['access_token'], user_id=user_id)
        if not uok and fb.get('backup_token'):
            db.log_activity(user_id, "WARNING", f"Primary token failed on manual upload. Retrying Backup Token on Page {fb['page_id']}...")
            uok, pid, uerr = upload_to_fb(path, final_title, final_desc, fb['page_id'], fb['backup_token'], user_id=user_id)
            
        db.record_upload(user_id, vid, final_title, video_url, fb['page_id'], pid, 'success' if uok else 'failed', uerr)
        if uok:
            posted_count += 1
            db.log_activity(user_id, "INFO", f"Manual post uploaded to FB Page {fb['page_id']}! Video ID: {pid}")
        else:
            db.log_activity(user_id, "ERROR", f"Manual post failed on FB Page {fb['page_id']}: {uerr}")
            
    try: os.remove(path)
    except: pass
    db.log_activity(user_id, "INFO", f"Manual post finished. Uploaded to {posted_count} Facebook page(s).")
    db.set_setting(user_id, "active_progress", f"✅ Post uploaded to {posted_count} page(s)!")

def run_sync_all_users():
    """Scheduled job: run sync for ALL users who have active channels."""
    cleanup()
    user_ids = db.get_all_active_user_ids()
    for uid in user_ids:
        try:
            run_sync_for_user(uid)
        except Exception as e:
            db.log_activity(uid, "ERROR", f"Sync error: {e}")
    cleanup()

def start_scheduler():
    global scheduler
    if scheduler is None:
        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(run_sync_all_users, 'interval', hours=1, id='global_sync')
        scheduler.start()

def restart_scheduler(hours):
    global scheduler
    if scheduler:
        try: scheduler.remove_job('global_sync')
        except: pass
        scheduler.add_job(run_sync_all_users, 'interval', hours=float(hours), id='global_sync')
