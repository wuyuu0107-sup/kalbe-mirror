# chat/repo.py
from __future__ import annotations
import os
import psycopg
from typing import Any, Dict, List, Tuple


class DB:
    """
    Thin psycopg3 wrapper.
    - Enforces read-only (SELECT) for fetch methods.
    - Adds a `query()` method that returns both rows AND column names,
      which helps the service format natural-language answers.
    """
    def __init__(self):
        self.conn: psycopg.Connection | None = None

    def _ensure_conn(self) -> None:
        if self.conn is None:
            dsn = os.getenv("DATABASE_URL")
            if not dsn:
                raise RuntimeError("DATABASE_URL is not set")
            # autocommit=True so SELECTs are fine without explicit tx mgmt
            self.conn = psycopg.connect(dsn, autocommit=True)

    def fetch_one(self, sql: str, params: List[Any] | None = None) -> Tuple[Any, ...] | None:
        self._ensure_conn()
        if not sql.strip().lower().startswith("select"):
            raise ValueError("read-only only")
        with self.conn.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchone()

    def fetch_all(self, sql: str, params: List[Any] | None = None) -> List[Tuple[Any, ...]]:
        self._ensure_conn()
        if not sql.strip().lower().startswith("select"):
            raise ValueError("read-only only")
        with self.conn.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()

    def query(self, sql: str, params: List[Any] | None = None) -> Dict[str, Any]:
        """
        Run a SELECT and return: {"rows": list[tuple], "columns": list[str]}
        """
        self._ensure_conn()
        if not sql.strip().lower().startswith("select"):
            raise ValueError("read-only only")
        with self.conn.cursor() as cur:
            cur.execute(sql, params or [])
            rows = cur.fetchall()
            cols = [d.name for d in cur.description] if cur.description else []
            return {"rows": rows, "columns": cols}
