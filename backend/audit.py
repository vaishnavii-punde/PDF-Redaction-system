import sqlite3, json
from datetime import datetime

DB_PATH = "audit.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS redactions (
            id TEXT PRIMARY KEY,
            filename TEXT,
            timestamp TEXT,
            findings TEXT,
            count INTEGER
        )
    """)
    conn.commit()
    conn.close()

def log_redaction(file_id, filename, findings):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO redactions VALUES (?,?,?,?,?)",
        (file_id, filename, datetime.now().isoformat(), json.dumps(findings), len(findings))
    )
    conn.commit()
    conn.close()

def get_all_logs():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, filename, timestamp, count FROM redactions ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()
    return [{"id": r[0], "filename": r[1], "timestamp": r[2], "count": r[3]} for r in rows]
