# Troubleshooting: YouTube Download Failures on Render

## "Sign in to confirm you're not a bot" / bot-detection errors

### Why this happens on cloud hosts but not locally

YouTube uses your **IP address reputation** as a primary bot-detection signal.
Home/mobile IPs have a good reputation because millions of real users share
those IP ranges. Render's servers (and all cloud/datacenter providers like AWS,
GCP, Heroku, Railway, etc.) use IP ranges that are **flagged as datacenter IPs**
— YouTube trusts them far less, even when you send a valid logged-in cookie.

There is no permanent fix for this. It is an ongoing cat-and-mouse problem.

---

## How to re-export fresh cookies when this error recurs

> **Do NOT commit `cookies.txt` to git.** It contains your YouTube session token
> and giving it to anyone is equivalent to handing them your password.

### Step-by-step

1. **Open a Private / Incognito browser window** (important — this avoids
   contaminating your main session).
2. Go to [youtube.com](https://youtube.com) and **log in** to the YouTube
   account the app uses.
3. Install the **"Get cookies.txt LOCALLY"** browser extension
   ([Chrome](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) /
   [Firefox](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)).
4. Click the extension icon -> **Export** -> save the file as `cookies.txt`.
5. Go to **Render Dashboard -> your service -> Environment -> Secret Files**.
6. Create or update a secret file with:
   - **Filename:** `cookies.txt`
   - **Mount path:** `/etc/secrets/cookies.txt`
   - **Contents:** paste the contents of the exported `cookies.txt`
7. Click **Save** — Render will automatically redeploy your service.

The app reads the cookie path from the `COOKIES_FILE_PATH` environment variable
(defaulting to `/etc/secrets/cookies.txt`), so no code changes are needed.

---

## Why this needs periodic maintenance

YouTube changes its bot-detection algorithms frequently. Even with valid cookies:

- Cookies **expire** after roughly 1-3 months.
- YouTube can **invalidate a session** if it detects unusual access patterns
  (many requests in a short time from a datacenter IP).
- YouTube ships anti-bot updates that may require a **yt-dlp update** — this is
  why `yt-dlp` is unpinned in `requirements.txt` (latest version installs on
  every deploy).

**Expected maintenance cadence:** re-export cookies every 4-8 weeks, or
immediately when you see "Sign in to confirm you're not a bot" in the Activity
Logs.

---

## What the Activity Logs will show

| Log message | What it means |
|---|---|
| `cookies=YES(3300B) header=# Netscape HTTP Cookie File` | Cookie file found and valid |
| `cookies=NO_FILE` | Cookie file missing - upload to Render Secret Files |
| `YouTube bot-detection triggered - cookies may be expired` | Re-export cookies (see above) |
| `SUCCESS T1[android+cookies]` | Download worked - no action needed |

---

## Checking if cookies.txt is in your git history (security audit)

If `cookies.txt` was ever committed by mistake, your YouTube session is
**compromised** — anyone with access to the repo can impersonate you. Fix it:

```bash
# See if cookies.txt is in history
git log --all --full-history -- cookies.txt

# If it appears, purge it from all history (destructive)
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch cookies.txt" \
  --prune-empty --tag-name-filter cat -- --all

git push origin --force --all

# Then immediately log out of that YouTube account on all devices
# and log back in to generate a new session.
```

After purging, re-export cookies from a fresh login as described above.
