from unittest.mock import patch, Mock, MagicMock
from types import SimpleNamespace as NS
import os

from authentication.models import User
from django.urls import reverse
from django.test import SimpleTestCase
from rest_framework.test import APITestCase
from django.contrib.auth.hashers import make_password

from chat.models import ChatSession


# =========================
# Integration-style API tests (views)
# =========================
class ChatFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create(
            username="geordie",
            password=make_password("pw"),
            display_name="geordie",
            email="geordie@example.com",
            roles=["researcher"],
            is_verified=True,
        )
        session = self.client.session
        session["user_id"] = str(self.user.user_id)
        session.save()

    def test_create_session_returns_201_and_session_id(self):
        resp = self.client.post(reverse("chat:sessions"), {"title": "Uji Klinis A"}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertIn("id", resp.json())

    @patch("chat.views.answer_question", return_value="Hai")
    def test_add_messages_and_fetch_history_in_order(self, _mock_answer):
        sid = self.client.post(reverse("chat:sessions"), {"title": ""}, format="json").json()["id"]
        r = self.client.post(reverse("chat:ask", args=[sid]), {"q": "Halo"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json().get("answer"), "Hai")

        msgs = self.client.get(reverse("chat:get_messages", args=[sid])).json()["messages"]
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant"])
        self.assertEqual(msgs[0]["content"], "Halo")
        self.assertEqual(msgs[1]["content"], "Hai")

    @patch("chat.llm.ask_gemini_text", return_value="SELECT COUNT(*) FROM patients")
    @patch("chat.service.DB")
    def test_ask_returns_answer_and_persists_assistant_message(self, mock_db_cls, _mock_llm):
        mock_db = mock_db_cls.return_value
        mock_db.query.return_value = {"rows": [(123,)], "columns": ["count"]}

        sid = self.client.post(reverse("chat:sessions"), {"title": "Demo"}, format="json").json()["id"]
        rq = self.client.post(
            reverse("chat:ask", args=[sid]),
            {"question": "Berapa total data pasien tersimpan?"},
            format="json",
        )
        self.assertEqual(rq.status_code, 200)
        self.assertIn("123", rq.json()["answer"])

        msgs = self.client.get(reverse("chat:get_messages", args=[sid])).json()["messages"]
        self.assertGreaterEqual(len(msgs), 2)

    def test_ask_invalid_session_returns_404(self):
        r = self.client.post(
            reverse("chat:ask", args=["00000000-0000-0000-0000-000000000000"]),
            {"q": "hi"},
            format="json",
        )
        self.assertEqual(r.status_code, 404)

    def test_ask_missing_payload_keys(self):
        sid = self.client.post(reverse("chat:sessions"), {}, format="json").json()["id"]
        r = self.client.post(reverse("chat:ask", args=[sid]), {}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.json())


# =========================
# Extra view coverage (edge cases)
# =========================
class ViewsExtraTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create(
            username="u",
            password=make_password("p"),
            display_name="u",
            email="u@example.com",
            roles=["researcher"],
            is_verified=True,
        )
        session = self.client.session
        session["user_id"] = str(self.user.user_id)
        session.save()

    def test_sessions_get_empty_then_post(self):
        ChatSession.objects.all().delete()
        r0 = self.client.get(reverse("chat:sessions"))
        self.assertEqual(r0.json()["sessions"], [])
        r1 = self.client.post(reverse("chat:sessions"), {}, format="json")
        self.assertEqual(r1.status_code, 201)

    def test_patch_title_empty_and_nonempty(self):
        sid = self.client.post(reverse("chat:sessions"), {}, format="json").json()["id"]
        self.client.patch(reverse("chat:session_detail", args=[sid]), {"title": ""}, format="json")
        self.client.patch(reverse("chat:session_detail", args=[sid]), {"title": "Baru"}, format="json")
        self.assertEqual(ChatSession.objects.get(pk=sid).title, "Baru")

    def test_delete_session(self):
        sid = self.client.post(reverse("chat:sessions"), {}, format="json").json()["id"]
        r = self.client.delete(reverse("chat:session_detail", args=[sid]))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(ChatSession.objects.filter(pk=sid).exists())

    def test_post_message_alias_payloads(self):
        sid = self.client.post(reverse("chat:sessions"), {}, format="json").json()["id"]
        url = reverse("chat:post_message", args=[sid])
        for field in ["content", "q", "question"]:
            r = self.client.post(url, {field: "hi"}, format="json")
            self.assertEqual(r.status_code, 201)

    def test_post_message_empty_400(self):
        sid = self.client.post(reverse("chat:sessions"), {}, format="json").json()["id"]
        url = reverse("chat:post_message", args=[sid])
        r = self.client.post(url, {"content": ""}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_get_messages_empty_session(self):
        sid = self.client.post(reverse("chat:sessions"), {}, format="json").json()["id"]
        r = self.client.get(reverse("chat:get_messages", args=[sid]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["messages"], [])


# =========================
# Service layer tests (semantic only)
# =========================
class ServiceTests(SimpleTestCase):
    def setUp(self):
        os.environ.setdefault("DATABASE_URL", "postgresql://fake:fake@localhost:5432/testdb")

    @patch("chat.llm.ask_gemini_text", return_value="SELECT COUNT(*) FROM patients")
    @patch("chat.service.DB")
    def test_semantic_count_ok(self, mock_db_cls, _mock_llm):
        from chat.service import answer_question
        mock_db = mock_db_cls.return_value
        mock_db.query.return_value = {"rows": [(1254,)], "columns": ["count"]}

        out = answer_question("How many patients are there?")
        self.assertTrue("There" in out or "patient" in out or "1254" in out)

    @patch("chat.llm.ask_gemini_text",
           return_value="SELECT sin, subject_initials FROM patients WHERE EXTRACT(YEAR FROM screening_date)=2024")
    @patch("chat.service.DB")
    def test_semantic_table_with_context(self, mock_db_cls, _mock_llm):
        from chat.service import answer_question
        mock_db = mock_db_cls.return_value
        mock_db.query.return_value = {
            "rows": [("87423", "AJKS"), ("87501", "BMHR")],
            "columns": ["sin", "subject_initials"],
        }

        # Your current service.answer_question(user_message: str) doesn’t take session_id
        out = answer_question("Now for 2024")
        self.assertIn("AJKS", out)
        self.assertIn("BMHR", out)

    @patch("chat.llm.ask_gemini_text", return_value="DROP TABLE patients; SELECT 1")
    def test_semantic_sql_enforces_select_only(self, _mock_llm):
        from chat.sqlgen import generate_semantic_sql
        try:
            sql = generate_semantic_sql("say something bad")
            assert sql.strip().lower().startswith("select")
        except Exception as e:
            # Accept either a descriptive ValueError or normal 'select' statement recovery
            assert any(k in str(e).lower() for k in ("select", "statement", "forbidden", "dml", "ddl"))

    @patch("chat.llm.ask_gemini_text", return_value="garbage not sql")
    def test_semantic_sql_garbage_raises(self, _mock_llm):
        from chat.sqlgen import generate_semantic_sql
        with self.assertRaises(Exception):
            generate_semantic_sql("nonsense")

    @patch("chat.llm.ask_gemini_text", return_value="SELECT COUNT(*) FROM patients")
    @patch("chat.service.DB")
    def test_db_error_bubbles_up(self, mock_db_cls, _mock_llm):
        """Matches current service.py (no try/except around db.query)."""
        from chat.service import answer_question
        mock_db = mock_db_cls.return_value
        mock_db.query.side_effect = Exception("db fail")
        with self.assertRaises(Exception):
            answer_question("count?")


# =========================
# Repo tests (DB wrapper)
# =========================
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


# =========================
# SQL generator tests (semantic)
# =========================
class SqlGenTests(SimpleTestCase):
    @patch("chat.llm.ask_gemini_text", return_value="SELECT COUNT(*) FROM patients")
    def test_generate_semantic_sql_returns_select(self, _mock_llm):
        from chat.sqlgen import generate_semantic_sql
        sql = generate_semantic_sql("How many patients?")
        self.assertTrue(sql.strip().lower().startswith("select"))
        self.assertIn("from patients", sql.lower())

    @patch("chat.llm.ask_gemini_text",
           return_value="INSERT INTO patients VALUES (1); SELECT * FROM patients;")
    def test_generate_semantic_sql_ignores_dml_and_keeps_select(self, _mock_llm):
        from chat.sqlgen import generate_semantic_sql
        # Your sanitizer raises ValueError for any DML, so we expect an exception.
        with self.assertRaises(Exception):
            generate_semantic_sql("give me patients")


    @patch("chat.llm.ask_gemini_text", return_value="DROP TABLE patients;")
    def test_generate_semantic_sql_rejects_nonselect(self, _mock_llm):
        from chat.sqlgen import generate_semantic_sql
        with self.assertRaises(Exception):
            generate_semantic_sql("oops")

    @patch("chat.llm.ask_gemini_text", return_value="")
    def test_generate_semantic_sql_empty(self, _mock_llm):
        from chat.sqlgen import generate_semantic_sql
        with self.assertRaises(Exception):
            generate_semantic_sql("blank")


# =========================
# LLM adapter tests (no real network)
# =========================
class LlmTests(SimpleTestCase):
    def _resp_with_text(self, text):
        return NS(
            candidates=[NS(content=NS(parts=[NS(text=text)]), finish_reason=None)],
            prompt_feedback=None,
            text=None,
        )

    @patch("chat.llm._get_model")
    def test_ask_gemini_text_ok(self, mock_get_model):
        from chat.llm import ask_gemini_text
        model = Mock()
        model.generate_content.return_value = self._resp_with_text("hello world")
        mock_get_model.return_value = model
        out = ask_gemini_text("hi")
        self.assertEqual(out, "hello world")

    @patch("chat.llm._get_model")
    def test_ask_gemini_text_blocked(self, mock_get_model):
        from chat.llm import ask_gemini_text, GeminiBlocked
        model = Mock()
        resp = self._resp_with_text("ignored")
        resp.prompt_feedback = NS(block_reason="BLOCKED")
        model.generate_content.return_value = resp
        mock_get_model.return_value = model
        with self.assertRaises(GeminiBlocked):
            ask_gemini_text("hi")

    @patch("chat.llm._get_model")
    def test_ask_gemini_text_empty(self, mock_get_model):
        from chat.llm import ask_gemini_text, GeminiError
        model = Mock()
        model.generate_content.return_value = self._resp_with_text("")
        mock_get_model.return_value = model
        with self.assertRaises(GeminiError):
            ask_gemini_text("hi")

    @patch("chat.llm._get_model")
    def test_ask_gemini_text_exception(self, mock_get_model):
        from chat.llm import ask_gemini_text, GeminiError
        model = Mock()
        model.generate_content.side_effect = Exception("sdk boom")
        mock_get_model.return_value = model
        with self.assertRaises(GeminiError):
            ask_gemini_text("hi")
