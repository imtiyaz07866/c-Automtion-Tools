import sqlite3, os

DB_PATH = r"c:\Automtion Tools\automation.db"

if os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    print("=== USERS ===")
    for u in c.execute("SELECT id, username, email, is_approved, is_admin FROM users").fetchall():
        print(dict(u))
        
    print("\n=== FB CREDENTIALS ===")
    for f in c.execute("SELECT * FROM fb_credentials").fetchall():
        print(dict(f))
        
    print("\n=== CHANNELS ===")
    for ch in c.execute("SELECT * FROM channels").fetchall():
        print(dict(ch))
        
    print("\n=== SETTINGS ===")
    for s in c.execute("SELECT * FROM settings").fetchall():
        print(dict(s))
else:
    print("automation.db not found!")
