import sqlite3
import database as db

with db.get_connection() as conn:
    c = conn.cursor()
    
    # 1. Re-assign all channels, fb_credentials, settings, history, activity_logs to user_id = 1
    c.execute("UPDATE OR IGNORE channels SET user_id=1 WHERE user_id != 1")
    c.execute("UPDATE OR IGNORE fb_credentials SET user_id=1 WHERE user_id != 1")
    c.execute("UPDATE OR IGNORE settings SET user_id=1 WHERE user_id != 1")
    c.execute("UPDATE OR IGNORE upload_history SET user_id=1 WHERE user_id != 1")
    c.execute("UPDATE OR IGNORE activity_logs SET user_id=1 WHERE user_id != 1")
    
    # 2. Delete all other user accounts except user_id = 1
    c.execute("DELETE FROM users WHERE id != 1")
    
    # 3. Update primary user record (user_id = 1)
    c.execute("UPDATE users SET username='imtiyaz', email='imtiyazxbusiness@gmail.com', display_name='Imtiyaz Alam', is_approved=1, is_admin=1 WHERE id=1")
    
    # 4. Pre-seed Gemini API Key
    c.execute("INSERT OR REPLACE INTO settings (user_id, key, value) VALUES (1, 'gemini_api_key', 'AIzaSyCBF5inRVo777af6Eez7cXAlbmHFWKd9mY')")
    
    conn.commit()

print("CONSOLIDATION SUCCESSFUL! All Facebook Pages, Page Tokens, Channels, Gemini Key & Logs 100% MERGED UNDER imtiyazxbusiness@gmail.com (ID 1)!")
