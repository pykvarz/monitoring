import sqlite3
import os

db_path = "hosts.db"

if not os.path.exists(db_path):
    print(f"Database {db_path} does not exist!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("SELECT COUNT(*) FROM hosts")
    count = cursor.fetchone()[0]
    print(f"Total hosts in DB: {count}")

    cursor.execute("SELECT id, name, ip, status FROM hosts")
    rows = cursor.fetchall()
    print("Hosts:")
    for row in rows:
        print(row)

except Exception as e:
    print(f"Error querying DB: {e}")
finally:
    conn.close()
