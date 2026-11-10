import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from app.config import DATABASE_PATH

def connect():
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_session_time ON conversations(session_id, created_at)")

def save_message(session_id: str, role: str, content: str):
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            "INSERT INTO conversations(session_id, role, content, created_at) VALUES(?,?,?,?)",
            (session_id, role, content, timestamp)
        )
    return timestamp

def get_recent_messages(session_id: str, limit: int = 16):
    with connect() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM conversations WHERE session_id=? ORDER BY id DESC LIMIT ?",
            (session_id, limit)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]

def search_memory(session_id: str, query: str, limit: int = 6):
    # Lightweight lexical retrieval; no embedding service or second agent tool.
    terms = [t.strip(".,?!:;()[]{}").lower() for t in query.split()]
    terms = [t for t in terms if len(t) > 3][:8]
    if not terms:
        return []
    clauses = " OR ".join(["LOWER(content) LIKE ?" for _ in terms])
    params = [session_id] + [f"%{t}%" for t in terms] + [limit]
    with connect() as conn:
        rows = conn.execute(
            f"SELECT role, content, created_at FROM conversations WHERE session_id=? AND ({clauses}) ORDER BY id DESC LIMIT ?",
            params
        ).fetchall()
    return [dict(r) for r in rows]

def list_sessions():
    with connect() as conn:
        return conn.execute("""
            SELECT session_id, MIN(created_at) AS started_at, MAX(created_at) AS last_active,
                   COUNT(*) AS message_count
            FROM conversations GROUP BY session_id ORDER BY last_active DESC
        """).fetchall()
