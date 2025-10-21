# chat/repo.py
import os
import psycopg

class DB:
    def __init__(self):
        self.conn = None

    def _ensure_conn(self):
        if self.conn is None:
            dsn = os.getenv("DATABASE_URL")
            if not dsn:
                raise RuntimeError("DATABASE_URL is not set")
            self.conn = psycopg.connect(dsn, autocommit=True)

    def fetch_one(self, sql, params=None):
        self._ensure_conn()
        if not sql.strip().lower().startswith("select"):
            raise ValueError("read-only only")
        with self.conn.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchone()

    def fetch_all(self, sql, params=None):
        self._ensure_conn()
        if not sql.strip().lower().startswith("select"):
            raise ValueError("read-only only")
        with self.conn.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()
