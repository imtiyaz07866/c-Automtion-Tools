import sqlite3
import os
import database as db

with db.get_connection() as conn:
    c = conn.cursor()
    
    # 1. Set user 1 email to imtiyazxbusiness@gmail.com
    c.execute("UPDATE users SET email='imtiyazxbusiness@gmail.com', display_name='Imtiyaz Alam', is_approved=1, is_admin=1 WHERE id=1")
    
    # 2. Update any other users with imzkbusiness to imtiyazxbusiness@gmail.com
    c.execute("UPDATE users SET email='imtiyazxbusiness@gmail.com' WHERE email LIKE '%imzkbusiness%' OR email LIKE '%imzbusiness%'")

    # 3. Transfer any channels, fb_credentials, upload_history, activity_logs to user_id=1
    for table in ['channels', 'fb_credentials', 'upload_history', 'activity_logs']:
        c.execute(f"UPDATE OR IGNORE {table} SET user_id=1 WHERE user_id != 1")

    conn.commit()

print("DATA MIGRATION SUCCESSFUL FOR imtiyazxbusiness@gmail.com!")
