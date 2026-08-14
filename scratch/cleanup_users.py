import sqlite3
import database as db

with db.get_connection() as conn:
    c = conn.cursor()
    
    # 1. Delete all non-admin / dummy users except imtiyazxbusiness@gmail.com
    c.execute("DELETE FROM users WHERE email != 'imtiyazxbusiness@gmail.com' AND username != 'imtiyaz'")
    
    # 2. Ensure user 1 has email imtiyazxbusiness@gmail.com, is_admin=1, is_approved=1
    c.execute("UPDATE users SET email='imtiyazxbusiness@gmail.com', display_name='Imtiyaz Alam', is_approved=1, is_admin=1 WHERE email='imtiyazxbusiness@gmail.com' OR username='imtiyaz'")
    
    # 3. Clean orphan records
    c.execute("DELETE FROM channels WHERE user_id NOT IN (SELECT id FROM users)")
    c.execute("DELETE FROM fb_credentials WHERE user_id NOT IN (SELECT id FROM users)")
    c.execute("DELETE FROM upload_history WHERE user_id NOT IN (SELECT id FROM users)")
    c.execute("DELETE FROM settings WHERE user_id NOT IN (SELECT id FROM users)")
    c.execute("DELETE FROM activity_logs WHERE user_id NOT IN (SELECT id FROM users)")
    
    conn.commit()

print("CLEANUP SUCCESSFUL! Only imtiyazxbusiness@gmail.com remains as Super Admin.")
