import yt_dlp, os

url = "https://www.youtube.com/watch?v=70Dj8S2zB5Q"
out = "c:\\Automtion Tools\\temp_test_70Dj8S2zB5Q.%(ext)s"

opts = {
    'format': 'bestvideo+bestaudio/best',
    'outtmpl': out,
    'quiet': False,
    'no_warnings': False,
    'nocheckcertificate': True,
    'geo_bypass': True,
    'extractor_args': {'youtube': {'player_client': ['android', 'mweb', 'creator']}}
}

print("Attempting download with pure android/mweb/creator clients...")
try:
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        print("DOWNLOAD SUCCESSFUL! Title:", info.get('title'))
except Exception as e:
    print("DOWNLOAD FAILED:", e)
