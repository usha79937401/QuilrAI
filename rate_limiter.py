"""Atomic SQLite sliding-window token limiter."""
import asyncio
import time
from contextlib import closing
from .database import TokenDatabase


class RateLimitExceeded(Exception):
    pass


class SlidingWindowTokenLimiter:
    def __init__(self, db: TokenDatabase, limit: int = 50_000, window_seconds: int = 60):
        self.db = db
        self.limit = limit
        self.window_seconds = window_seconds
        self._lock = asyncio.Lock()

    async def reserve(self, tenant_key: str, tokens: int, now: float | None = None):
        if not tenant_key or tokens < 0:
            raise ValueError("tenant_key is required and tokens cannot be negative")
        if tokens > self.limit:
            raise RateLimitExceeded("Single request exceeds tenant token limit")
        now = time.time() if now is None else now
        cutoff = now - self.window_seconds
        async with self._lock:
            with closing(self.db.connect()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    conn.execute("DELETE FROM token_events WHERE created_at <= ?", (cutoff,))
                    row = conn.execute(
                        "SELECT COALESCE(SUM(tokens), 0) FROM token_events WHERE tenant_key=? AND created_at>?",
                        (tenant_key, cutoff),
                    ).fetchone()
                    used = int(row[0])
                    if used + tokens > self.limit:
                        conn.execute("ROLLBACK")
                        raise RateLimitExceeded(f"Tenant token limit exceeded ({used}/{self.limit} used)")
                    conn.execute(
                        "INSERT INTO token_events(tenant_key, tokens, created_at) VALUES (?, ?, ?)",
                        (tenant_key, tokens, now),
                    )
                    conn.execute("COMMIT")
                    return {"tenant": tenant_key, "used_before": used, "reserved": tokens,
                            "remaining": self.limit - used - tokens}
                except Exception:
                    if conn.in_transaction:
                        conn.execute("ROLLBACK")
                    raise
