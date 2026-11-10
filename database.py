"""SQLite persistence for token events."""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS token_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_key TEXT NOT NULL,
    tokens INTEGER NOT NULL CHECK(tokens >= 0),
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_token_events_tenant_time
ON token_events(tenant_key, created_at);
"""


class TokenDatabase:
    def __init__(self, path: str = "token_usage.sqlite3"):
        self.path = path
        conn = self.connect()
        try:
            conn.executescript(SCHEMA)
        finally:
            conn.close()

    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn
