import yt_dlp

url = "https://www.youtube.com/watch?v=70Dj8S2zB5Q"

ua_android = 'com.google.android.youtube/19.29.37 (Linux; U; Android 11; en_US) gzip'
ua_ios = 'com.google.ios.youtube/19.29.1 (iPhone14,3; U; CPU iOS 17_5_1 like Mac OS X; en_US)'

configs = [
    ("Android App UA + android client", ua_android, ['android']),
    ("Android App UA + android,mweb clients", ua_android, ['android', 'mweb']),
    ("iOS App UA + ios,android clients", ua_ios, ['ios', 'android'])
]

for name, ua, clients in configs:
    print(f"\n--- Testing {name} ---")
    opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        'user_agent': ua,
        'extractor_args': {'youtube': {'player_client': clients}}
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            print(f"SUCCESS! Title: {info.get('title')}")
    except Exception as e:
        print(f"FAILED: {e}")
