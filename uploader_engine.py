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

def fetch_latest_videos(channel_url, max_results=3):
    opts = {'extract_flat': 'in_playlist', 'skip_download': True, 'quiet': True, 'no_warnings': True, 'playlistend': max_results}
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

def download_video(video_url, video_id):
    out = os.path.join(TEMP_DIR, f"{video_id}.%(ext)s")
    ff_path = get_ffmpeg_path()
    
    opts = {
        'format': 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
        'outtmpl': out,
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
    }
    if ff_path:
        opts['ffmpeg_location'] = ff_path
        opts['merge_output_format'] = 'mp4'

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            fn = ydl.prepare_filename(info)
            base, _ = os.path.splitext(fn)
            mp4 = f"{base}.mp4"
            if os.path.exists(mp4): return True, mp4, info.get('title',''), info.get('description','')
            if os.path.exists(fn): return True, fn, info.get('title',''), info.get('description','')
            m = glob.glob(os.path.join(TEMP_DIR, f"{video_id}.*"))
            if m: return True, m[0], info.get('title',''), info.get('description','')
    except Exception as e:
        # Fallback to single stream format requiring no ffmpeg merging
        try:
            opts_fallback = {
                'format': 'best',
                'outtmpl': out,
                'quiet': True,
                'no_warnings': True,
            }
            if ff_path:
                opts_fallback['ffmpeg_location'] = ff_path
            with yt_dlp.YoutubeDL(opts_fallback) as ydl:
                info = ydl.extract_info(video_url, download=True)
                fn = ydl.prepare_filename(info)
                base, _ = os.path.splitext(fn)
                mp4 = f"{base}.mp4"
                if os.path.exists(mp4): return True, mp4, info.get('title',''), info.get('description','')
                if os.path.exists(fn): return True, fn, info.get('title',''), info.get('description','')
                m = glob.glob(os.path.join(TEMP_DIR, f"{video_id}.*"))
                if m: return True, m[0], info.get('title',''), info.get('description','')
        except Exception as err2:
            return False, str(err2), "", ""

    return False, "File not found", "", ""

def upload_to_fb(file_path, title, desc, page_id, token):
    url = f"https://graph-video.facebook.com/v19.0/{page_id}/videos"
    payload = {'title': (title or "Video")[:255], 'description': f"{title}\n\n{(desc or '')[:400]}", 'access_token': token}
    try:
        with open(file_path, 'rb') as f:
            r = requests.post(url, data=payload, files={'source': f}, timeout=600)
        j = r.json()
        if r.status_code == 200 and 'id' in j:
            return True, j['id'], None
        err = j.get('error', {}).get('message', r.text)
        return False, None, err
    except Exception as e:
        return False, None, str(e)

def run_sync_for_user(user_id):
    """Run sync for a specific user."""
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
        db.log_activity(user_id, "INFO", f"Checking: {ch['channel_url']}")
        target_pages = ch.get('target_fb_pages', 'all') or 'all'
        target_ids = [p.strip() for p in target_pages.split(',')] if target_pages != 'all' else None

        for vid in fetch_latest_videos(ch['channel_url'], mx):
            for fb in fb_creds:
                if target_ids and fb['page_id'] not in target_ids:
                    continue
                if db.is_video_processed(user_id, vid['id'], fb['page_id']): continue
                db.log_activity(user_id, "INFO", f"New video: '{vid['title']}' -> FB {fb['page_id']}")
                ok, path, title, desc = download_video(vid['url'], vid['id'])
                if not ok:
                    db.record_upload(user_id, vid['id'], vid['title'], ch['channel_url'], fb['page_id'], None, 'failed', path)
                    db.log_activity(user_id, "ERROR", f"Download failed: {path}")
                    continue
                uok, pid, uerr = upload_to_fb(path, title or vid['title'], desc, fb['page_id'], fb['access_token'])
                if not uok and fb.get('backup_token'):
                    db.log_activity(user_id, "WARNING", f"Primary token failed for FB Page {fb['page_id']}. Trying Backup Token...")
                    uok, pid, uerr = upload_to_fb(path, title or vid['title'], desc, fb['page_id'], fb['backup_token'])
                    if uok:
                        db.log_activity(user_id, "INFO", f"Backup Token succeeded! Video ID: {pid}")

                db.record_upload(user_id, vid['id'], title or vid['title'], ch['channel_url'], fb['page_id'], pid, 'success' if uok else 'failed', uerr)
                if uok:
                    total += 1
                    db.log_activity(user_id, "INFO", f"Posted! FB Video ID: {pid}")
                else:
                    db.log_activity(user_id, "ERROR", f"FB upload failed on primary & backup: {uerr}")
                try: os.remove(path)
                except: pass
    db.log_activity(user_id, "INFO", f"Sync done. Posted: {total}")

import secrets

def run_manual_post_for_user(user_id, video_url, target_fb_pages="all", custom_title=None, custom_desc=None):
    """Manually post a specific video or latest video from channel to target FB pages."""
    db.log_activity(user_id, "INFO", f"Manual post process started for link: {video_url}")
    fb_creds = db.get_fb_credentials(user_id)
    if not fb_creds:
        db.log_activity(user_id, "WARNING", "No Facebook Page connected for manual upload.")
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
            return
            
    vid = "manual_" + secrets.token_hex(6)
    ok, path, yt_title, yt_desc = download_video(actual_url, vid)
    if not ok:
        db.log_activity(user_id, "ERROR", f"Manual video download failed: {path}")
        return
        
    final_title = (custom_title or yt_title or "Video Post").strip()
    final_desc = (custom_desc or yt_desc or "").strip()
    
    posted_count = 0
    for fb in fb_creds:
        if target_ids and fb['page_id'] not in target_ids:
            continue
            
        uok, pid, uerr = upload_to_fb(path, final_title, final_desc, fb['page_id'], fb['access_token'])
        if not uok and fb.get('backup_token'):
            db.log_activity(user_id, "WARNING", f"Primary token failed on manual upload. Retrying Backup Token on Page {fb['page_id']}...")
            uok, pid, uerr = upload_to_fb(path, final_title, final_desc, fb['page_id'], fb['backup_token'])
            
        db.record_upload(user_id, vid, final_title, video_url, fb['page_id'], pid, 'success' if uok else 'failed', uerr)
        if uok:
            posted_count += 1
            db.log_activity(user_id, "INFO", f"Manual post uploaded to FB Page {fb['page_id']}! Video ID: {pid}")
        else:
            db.log_activity(user_id, "ERROR", f"Manual post failed on FB Page {fb['page_id']}: {uerr}")
            
    try: os.remove(path)
    except: pass
    db.log_activity(user_id, "INFO", f"Manual post finished. Uploaded to {posted_count} Facebook page(s).")

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
