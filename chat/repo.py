import os, psycopg

class DB:
    def __init__(self):
        self.conn = psycopg.connect(os.getenv("DATABASE_URL"), autocommit=True)

    def fetch_one(self, sql, params=None):
        if not sql.strip().lower().startswith("select"):
            raise ValueError("read-only only")
        with self.conn.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchone()

    def fetch_all(self, sql, params=None):
        if not sql.strip().lower().startswith("select"):
            raise ValueError("read-only only")
        with self.conn.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()
