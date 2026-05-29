"""Configure Open Terminal connection directly in OpenWebUI's database."""
import sqlite3
import json
import os

DB_PATH = "/app/backend/data/webui.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print("Tables:", tables)

# Check for config table
if "config" in tables:
    cursor.execute("SELECT * FROM config")
    rows = cursor.fetchall()
    print(f"\nConfig rows: {len(rows)}")
    for row in rows:
        print(f"  {str(row)[:200]}")

# Check for terminal-related tables
for t in tables:
    if 'terminal' in t.lower():
        cursor.execute(f"SELECT * FROM {t}")
        print(f"\nTable '{t}':", cursor.fetchall())

# Look for any terminal-related data
for t in tables:
    try:
        cursor.execute(f"SELECT * FROM {t} LIMIT 5")
        rows = cursor.fetchall()
        for row in rows:
            s = str(row)
            if 'terminal' in s.lower():
                print(f"\nFound terminal in {t}: {s[:300]}")
    except:
        pass

# Check what the env var TERMINAL_SERVER_CONNECTIONS expects
# Look at the source code
import subprocess
result = subprocess.run(
    ["grep", "-r", "TERMINAL_SERVER_CONNECTIONS", "/app/backend/open_webui/"],
    capture_output=True, text=True
)
print("\n\nSource code references to TERMINAL_SERVER_CONNECTIONS:")
print(result.stdout[:2000] if result.stdout else "Not found")

conn.close()
