from unittest.mock import patch, MagicMock
import os
from django.test import SimpleTestCase

class RepoTests(SimpleTestCase):
    def setUp(self):
        os.environ.setdefault("DATABASE_URL", "postgresql://fake:fake@localhost:5432/testdb")

    @patch("chat.repo.psycopg")
    def test_fetch_one_ok(self, mock_psycopg):
        from chat.repo import DB
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = (7,)
        conn.cursor.return_value.__enter__.return_value = cur
        mock_psycopg.connect.return_value = conn
        db = DB()
        res = db.fetch_one("SELECT 1")
        self.assertEqual(res, (7,))

    @patch("chat.repo.psycopg")
    def test_fetch_all_ok(self, mock_psycopg):
        from chat.repo import DB
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchall.return_value = [(1,), (2,)]
        conn.cursor.return_value.__enter__.return_value = cur
        mock_psycopg.connect.return_value = conn
        db = DB()
        res = db.fetch_all("SELECT 1")
        self.assertEqual(res, [(1,), (2,)])

    @patch("chat.repo.psycopg.connect")
    def test_readonly_guard(self, _mock_connect):
        from chat.repo import DB
        with self.assertRaises(ValueError):
            DB().fetch_one("UPDATE patients SET age=30")

    @patch("chat.repo.psycopg.connect", side_effect=Exception("no dsn"))
    def test_missing_dsn(self, _):
        from chat.repo import DB
        if "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]
        db = DB()
        with self.assertRaises(RuntimeError):
            db.fetch_one("SELECT 1")


class RepoMoreTests(SimpleTestCase):
    def setUp(self):
        os.environ.setdefault("DATABASE_URL", "postgresql://fake:fake@localhost:5432/testdb")

    @patch("chat.repo.psycopg.connect")
    def test_query_returns_rows_and_columns(self, mock_connect):
        from chat.repo import DB

        # Build a fake cursor/connection with description objects
        class D: 
            def __init__(self, name): self.name = name

        cur = MagicMock()
        cur.fetchall.return_value = [(1, "a"), (2, "b")]
        cur.description = [D("id"), D("name")]

        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        mock_connect.return_value = conn

        db = DB()
        out = db.query("SELECT id, name FROM patients")
        self.assertEqual(out["rows"], [(1, "a"), (2, "b")])
        self.assertEqual(out["columns"], ["id", "name"])

    @patch("chat.repo.psycopg.connect")
    def test_query_description_none(self, mock_connect):
        from chat.repo import DB
        cur = MagicMock()
        cur.fetchall.return_value = []
        cur.description = None  # force the no-description branch
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        mock_connect.return_value = conn

        db = DB()
        out = db.query("SELECT 1")
        self.assertEqual(out["rows"], [])
        self.assertEqual(out["columns"], [])

    @patch("chat.repo.psycopg.connect")
    def test_fetch_one_none(self, mock_connect):
        from chat.repo import DB
        cur = MagicMock()
        cur.fetchone.return_value = None
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        mock_connect.return_value = conn

        db = DB()
        res = db.fetch_one("SELECT 1 WHERE 1=0")
        self.assertIsNone(res)

    def test_fetch_all_readonly_guard(self):
        from chat.repo import DB
        with self.assertRaises(ValueError):
            DB().fetch_all("UPDATE patients SET age=30")

    def test_query_readonly_guard(self):
        from chat.repo import DB
        with self.assertRaises(ValueError):
            DB().query("DELETE FROM patients")

    @patch("chat.repo.psycopg.connect")
    def test_params_forwarded(self, mock_connect):
        from chat.repo import DB
        cur = MagicMock()
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        mock_connect.return_value = conn

        db = DB()
        db.fetch_all("SELECT * FROM patients WHERE age > %s AND gender = %s", [30, "Male"])
        cur.execute.assert_called_once_with("SELECT * FROM patients WHERE age > %s AND gender = %s", [30, "Male"])
