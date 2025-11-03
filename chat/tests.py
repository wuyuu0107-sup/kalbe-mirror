from unittest.mock import patch, Mock, MagicMock
from types import SimpleNamespace as NS
import os
import sys
import uuid
import json

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

    @patch("chat.sqlgen.ask_gemini_text",
        return_value="SELECT sin, subject_initials FROM patients WHERE EXTRACT(YEAR FROM screening_date)=2024")
    @patch("chat.service.DB")
    def test_semantic_table_with_context(self, mock_db_cls, _mock_llm_sqlgen):
        from chat.service import answer_question

        mock_db = Mock()
        mock_db.query.return_value = {
            "rows": [(1, "A"), (2, "B")],
            "columns": ["sin", "subject_initials"]
        }
        mock_db_cls.return_value = mock_db

        out = answer_question("Now for 2024")
        self.assertIn("subject_initials", out)
        self.assertIn("sin", out)


    @patch("chat.sqlgen.ask_gemini_text", return_value="DROP TABLE patients; SELECT 1")
    def test_semantic_sql_enforces_select_only(self, _mock_llm_sqlgen):
        from chat.sqlgen import generate_semantic_sql
        with self.assertRaises(Exception):
            generate_semantic_sql("say something bad")

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
    @patch("chat.sqlgen.ask_gemini_text", return_value="SELECT COUNT(*) FROM patients")
    def test_generate_semantic_sql_returns_select(self, _mock_llm):
        from chat.sqlgen import generate_semantic_sql
        sql = generate_semantic_sql("How many patients?")
        self.assertTrue(sql.strip().lower().startswith("select"))
        self.assertIn("from patients", sql.lower())

    @patch("chat.sqlgen.ask_gemini_text",
        return_value="INSERT INTO patients VALUES (1); SELECT * FROM patients;")
    def test_generate_semantic_sql_ignores_dml_and_keeps_select(self, _mock_llm):
        from chat.sqlgen import generate_semantic_sql
        with self.assertRaises(Exception):
            generate_semantic_sql("give me patients")

    @patch("chat.sqlgen.ask_gemini_text", return_value="DROP TABLE patients;")
    def test_generate_semantic_sql_rejects_nonselect(self, _mock_llm):
        from chat.sqlgen import generate_semantic_sql
        with self.assertRaises(Exception):
            generate_semantic_sql("oops")


    @patch("chat.sqlgen.ask_gemini_text", return_value="")
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
# =========================
# Service branch coverage 
# =========================



class TestServiceBranch(SimpleTestCase):
    def _stub_pipeline(self, rows, cols):
        """Context manager that stubs generate_semantic_sql and DB().query()."""
        return patch.multiple(
            "chat.service",
            generate_semantic_sql=patch.DEFAULT,
            DB=patch.DEFAULT,
            spec_set=True,
        )

    # --- module init: locale.setlocale exception path (L11–14) ---
    def test_module_init_locale_fallback(self):
        import chat.service as svc
        with patch.object(svc.locale, "setlocale", side_effect=Exception("boom")):
            # Force a re-import to execute the try/except at import time.
            mod_name = svc.__name__
            sys.modules.pop(mod_name, None)
            import chat.service as reloaded  # noqa: F401

    # --- _human_int / _human_pct fallbacks (L16–31) ---
    def test_human_int_and_pct_fallbacks(self):
        from chat.service import _human_int, _human_pct
        self.assertTrue(_human_int("1234"))                  # locale-dependent grouping
        self.assertTrue(_human_int("12.7").isdigit())        # float->int fallback
        self.assertEqual(_human_int("not-a-number"), "not-a-number")
        self.assertEqual(_human_pct(1, 0), "0%")             # zero den
        self.assertEqual(_human_pct("bad", "value"), "0%")   # exception path

    # --- _render_table branches (L33–46) ---
    def test_render_table_empty_and_more_indicator(self):
        from chat.service import _render_table
        self.assertEqual(_render_table(["a", "b"], []), "(empty)")
        cols = ["c1", "c2", "c3"]
        rows = [(i, i + 1, i + 2) for i in range(10)]
        out = _render_table(cols, rows, max_rows=8)
        self.assertIn("... (", out)  # hits line 45

    # --- guard for "meaning of life" (L97–100) ---
    def test_guard_meaning_of_life(self):
        import chat.service as service
        out = service.answer_question("what is the meaning of life?")
        self.assertIn("clinical dataset", out)

    # --- no results (L112–114) ---
    @patch("chat.service.DB")
    @patch("chat.service.generate_semantic_sql", return_value="SELECT 1")
    def test_no_results_path(self, _gen, mock_db_cls):
        mock_db = mock_db_cls.return_value
        mock_db.query.return_value = {"rows": [], "columns": []}
        from chat.service import answer_question
        self.assertEqual(answer_question("show me something"), "No results found.")

    # --- scalar sentence path (L119–120 -> L48–53) ---
    @patch("chat.service.DB")
    @patch("chat.service.generate_semantic_sql", return_value="SELECT COUNT(*)")
    def test_scalar_sentence_path(self, _gen, mock_db_cls):
        mock_db = mock_db_cls.return_value
        mock_db.query.return_value = {"rows": [(123,)], "columns": ["count"]}
        from chat.service import answer_question
        out = answer_question("How many patient are there?")
        self.assertIn("unique patient entries", out)

    # --- group summary: 'most' branch (L56–69, L63–64) ---
    @patch("chat.service.DB")
    @patch("chat.service.generate_semantic_sql", return_value="SELECT grp, n")
    def test_group_summary_most_branch(self, _gen, mock_db_cls):
        mock_db = mock_db_cls.return_value
        mock_db.query.return_value = {
            "columns": ["group", "n"],
            "rows": [("A", 10), ("B", 25), ("C", 7)],
        }
        from chat.service import answer_question
        out = answer_question("Which group has the most?")
        self.assertIn("highest value", out)
        self.assertNotIn("Top group:", out)

    # --- group summary: else branch (L65–66) ---
    @patch("chat.service.DB")
    @patch("chat.service.generate_semantic_sql", return_value="SELECT grp, cnt")
    def test_group_summary_else_branch(self, _gen, mock_db_cls):
        mock_db = mock_db_cls.return_value
        mock_db.query.return_value = {
            "columns": ["grp", "cnt"],
            "rows": [("X", 1), ("Y", 2)],
        }
        from chat.service import answer_question
        self.assertIn("Top group:", answer_question("Show group summary"))

    # --- small cols table (L125–127) + "... (N more)" (L45) ---
    @patch("chat.service.DB")
    @patch("chat.service.generate_semantic_sql", return_value="SELECT c1,c2,c3")
    def test_small_cols_table_with_more_indicator(self, _gen, mock_db_cls):
        mock_db = mock_db_cls.return_value
        rows = [("r", i, i * 2) for i in range(12)]
        mock_db.query.return_value = {"columns": ["c1", "c2", "c3"], "rows": rows}
        from chat.service import answer_question
        out = answer_question("list rows")
        self.assertTrue(out.startswith("Found "))
        self.assertIn("... (", out)

    # --- large cols default path (L129–130) ---
    @patch("chat.service.DB")
    @patch("chat.service.generate_semantic_sql", return_value="SELECT many")
    def test_large_cols_default_path(self, _gen, mock_db_cls):
        mock_db = mock_db_cls.return_value
        cols = [f"c{i}" for i in range(6)]
        rows = [tuple(range(6)) for _ in range(3)]
        mock_db.query.return_value = {"columns": cols, "rows": rows}
        from chat.service import answer_question
        self.assertTrue(answer_question("anything").startswith("Here are the results:"))

    # --- percentage phrase: (a,b) pair (L76–79, L115–117) ---
    @patch("chat.service.DB")
    @patch("chat.service.generate_semantic_sql", return_value="SELECT a,b")
    def test_percentage_phrase_pair_row(self, _gen, mock_db_cls):
        mock_db = mock_db_cls.return_value
        mock_db.query.return_value = {"columns": ["a", "b"], "rows": [(25, 100)]}
        from chat.service import answer_question
        out = answer_question("what percentage is this?")
        self.assertIn("representing 25%", out)

    @patch("chat.service.DB")
    @patch("chat.service.generate_semantic_sql", return_value="SELECT *")
    def test_percentage_phrase_named_columns(self, _gen, mock_db_cls):
        mock_db = mock_db_cls.return_value
        mock_db.query.return_value = {
            "columns": ["id", "total_count", "female_count"],  # add an extra column
            "rows": [("row-1", 100, 55)],
        }
        from chat.service import answer_question
        out = answer_question("persentase perempuan?")
        self.assertIn("female patients, representing 55%", out)         # percentage text
        self.assertIn("of 100 participants", out)                       # total wording

    @patch("chat.service.DB")
    @patch("chat.service.generate_semantic_sql", return_value="SELECT col FROM patients")
    def test_maybe_percentage_phrase_no_keyword(self, _gen, mock_db_cls):
        """Covers early return None (no keyword)."""
        mock_db = mock_db_cls.return_value
        mock_db.query.return_value = {"columns": ["a", "b"], "rows": [(1, 2)]}
        from chat.service import answer_question
        out = answer_question("show summary of patients")
        # Expect _group_summary default branch:
        self.assertTrue(out.startswith("Top group:"))
        self.assertIn(" | ", out)  # has the rendered table below


    @patch("chat.service.DB")
    @patch("chat.service.generate_semantic_sql", return_value="SELECT weird FROM patients")
    def test_maybe_percentage_phrase_no_match_branch(self, _gen, mock_db_cls):
        """Covers final return None when conditions don't match."""
        mock_db = mock_db_cls.return_value
        mock_db.query.return_value = {"columns": ["weird_col"], "rows": [(10,)]}
        from chat.service import answer_question
        out = answer_question("percentage weird")
        # Falls back to scalar sentence path:
        self.assertTrue(out.startswith("The result is"))
        self.assertIn("10", out)

    @patch("chat.service.DB")
    @patch("chat.service.generate_semantic_sql", return_value="SELECT id,name,age FROM patients")
    def test_small_table_found_branch(self, _gen, mock_db_cls):
        """Covers the branch that returns 'Found N rows.' for small tables (1<cols<=5)."""
        mock_db = mock_db_cls.return_value
        mock_db.query.return_value = {
            "columns": ["id", "name", "age"],
            "rows": [(1, "John", 25), (2, "Alice", 30)],
        }
        from chat.service import answer_question
        out = answer_question("list all patients")
        assert out.startswith("Found 2 rows.")
        assert "John" in out and "Alice" in out

    def test_group_summary_fallback_for_non_2_col(self):
        from chat.service import _group_summary
        cols = ["a", "b", "c"]  # not 2 columns
        rows = [("x", 1, 2)]
        out = _group_summary("any question", cols, rows)
        self.assertTrue(out.startswith("Found 1 rows."))


# =========================
# LLM consolidated branch coverage (no dups)
# =========================
class LlmAllBranches(SimpleTestCase):
    def tearDown(self):
        # reset cached model between tests
        import chat.llm as llm
        llm._model = None

    # ---- helpers ----
    def _mk_resp(self, *, text=None, block_reason=None, finish_reason=None):
        parts = []
        if text is not None:
            parts = [NS(text=text)]
        content = NS(parts=parts)
        cand = NS(content=content, finish_reason=finish_reason)
        pf = None if block_reason is None else NS(block_reason=block_reason)
        return NS(candidates=[cand], prompt_feedback=pf, text=None)

    # ---- JSON/intent happy & repair path ----
    @patch("chat.llm._get_model")
    def test_get_intent_json_ok_and_repairs(self, mock_get_model):
        raw = """```json
        {'intent': 'TOTAL_PATIENTS', 'args': {'x': 1,},}
        ```"""
        model = Mock()
        model.generate_content.return_value = self._mk_resp(text=raw)
        mock_get_model.return_value = model

        from chat.llm import get_intent_json
        out = get_intent_json("berapa total pasien?")
        self.assertEqual(out, '{"intent":"TOTAL_PATIENTS","args":{"x":1}}')

    # ---- Blocked paths ----
    @patch("chat.llm._get_model")
    def test_get_intent_json_blocked_via_prompt_feedback(self, mock_get_model):
        model = Mock()
        model.generate_content.return_value = self._mk_resp(
            text='{"intent":"TOTAL_PATIENTS","args":{}}', block_reason="SAFETY"
        )
        mock_get_model.return_value = model
        from chat.llm import get_intent_json, GeminiBlocked
        with self.assertRaises(GeminiBlocked):
            get_intent_json("x")

    @patch("chat.llm._get_model")
    def test_get_intent_json_blocked_via_finish_reason(self, mock_get_model):
        model = Mock()
        model.generate_content.return_value = self._mk_resp(
            text='{"intent":"TOTAL_PATIENTS","args":{}}', finish_reason="SAFETY"
        )
        mock_get_model.return_value = model
        from chat.llm import get_intent_json, GeminiBlocked
        with self.assertRaises(GeminiBlocked):
            get_intent_json("x")

    @patch("chat.llm._get_model")
    def test_get_intent_json_finish_reason_blocked_literal(self, mock_get_model):
        # cover "blocked" (not only SAFETY)
        model = Mock()
        model.generate_content.return_value = self._mk_resp(
            text='{"intent":"ANY","args":{}}', finish_reason="BLOCKED"
        )
        mock_get_model.return_value = model
        from chat.llm import get_intent_json, GeminiBlocked
        with self.assertRaises(GeminiBlocked):
            get_intent_json("y")

    # ---- prompt_feedback present but no block_reason -> continue ----
    @patch("chat.llm._get_model")
    def test_get_intent_json_feedback_without_block_reason(self, mock_get_model):
        model = Mock()
        resp = NS(
            candidates=[NS(content=NS(parts=[NS(text='{"intent":"TOTAL_PATIENTS","args":{}}')]), finish_reason=None)],
            prompt_feedback=NS(block_reason=None),
            text=None,
        )
        model.generate_content.return_value = resp
        mock_get_model.return_value = model
        from chat.llm import get_intent_json
        out = get_intent_json("lanjut")
        self.assertEqual(out, '{"intent":"TOTAL_PATIENTS","args":{}}')

    # ---- Empty / invalid / bad schema ----
    @patch("chat.llm._get_model")
    def test_get_intent_json_empty_raises(self, mock_get_model):
        model = Mock()
        model.generate_content.return_value = self._mk_resp(text="  ")
        mock_get_model.return_value = model
        from chat.llm import get_intent_json, GeminiError
        with self.assertRaises(GeminiError):
            get_intent_json("x")

    @patch("chat.llm._get_model")
    def test_get_intent_json_invalid_json_raises(self, mock_get_model):
        model = Mock()
        model.generate_content.return_value = self._mk_resp(text="not json at all")
        mock_get_model.return_value = model
        from chat.llm import get_intent_json, GeminiError
        with self.assertRaises(GeminiError):
            get_intent_json("x")

    @patch("chat.llm._get_model")
    def test_get_intent_json_bad_schema_missing_intent(self, mock_get_model):
        model = Mock()
        model.generate_content.return_value = self._mk_resp(text='{"args":{}}')
        mock_get_model.return_value = model
        from chat.llm import get_intent_json, GeminiError
        with self.assertRaises(GeminiError):
            get_intent_json("no-intent")

    @patch("chat.llm._get_model")
    def test_get_intent_json_bad_schema_missing_args(self, mock_get_model):
        model = Mock()
        model.generate_content.return_value = self._mk_resp(text='{"intent":"X"}')
        mock_get_model.return_value = model
        from chat.llm import get_intent_json, GeminiError
        with self.assertRaises(GeminiError):
            get_intent_json("no-args")

    @patch("chat.llm._get_model")
    def test_get_intent_json_bad_schema_args_not_dict(self, mock_get_model):
        model = Mock()
        model.generate_content.return_value = self._mk_resp(text='{"intent":"X","args":1}')
        mock_get_model.return_value = model
        from chat.llm import get_intent_json, GeminiError
        with self.assertRaises(GeminiError):
            get_intent_json("x")

    # ---- finish_reason try/except generic Exception branch ----
    @patch("chat.llm._get_model")
    def test_get_intent_json_finish_reason_generic_except(self, mock_get_model):
        model = Mock()
        resp = NS(
            candidates=object(),  # `(candidates or [None])[0]` -> TypeError -> except Exception: pass
            prompt_feedback=None,
            text='{"intent":"TOTAL_PATIENTS","args":{}}',
        )
        model.generate_content.return_value = resp
        mock_get_model.return_value = model
        from chat.llm import get_intent_json
        out = get_intent_json("generic-except")
        self.assertEqual(out, '{"intent":"TOTAL_PATIENTS","args":{}}')

    # ---- resp.text fallback paths ----
    @patch("chat.llm._get_model")
    def test_get_intent_json_uses_resp_text(self, mock_get_model):
        import chat.llm as llm
        model = Mock()
        model.generate_content.return_value = NS(candidates=[], prompt_feedback=None, text='{"intent":"TOTAL_PATIENTS","args":{}}')
        mock_get_model.return_value = model
        out = llm.get_intent_json("pakai text")
        self.assertEqual(out, '{"intent":"TOTAL_PATIENTS","args":{}}')

    @patch("chat.llm._get_model")
    def test_get_intent_json_intent_none_stringified(self, mock_get_model):
        import chat.llm as llm
        model = Mock()
        model.generate_content.return_value = self._mk_resp(text='{"intent": null, "args": {}}')
        mock_get_model.return_value = model
        out = llm.get_intent_json("apa intentnya?")
        self.assertEqual(out, '{"intent":"None","args":{}}')

    # ---- app timeout guard ----
    def test_get_intent_json_app_timeout_maps(self):
        class _FakeFuture:
            def result(self, timeout=None):
                from concurrent.futures import TimeoutError as FUTimeout
                raise FUTimeout()
        class _FakeExecutor:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def submit(self, fn): return _FakeFuture()

        with patch("chat.llm._get_model") as gm, patch("chat.llm.ThreadPoolExecutor", return_value=_FakeExecutor()):
            model = Mock()
            gm.return_value = model
            from chat.llm import get_intent_json, GeminiUnavailable
            with self.assertRaises(GeminiUnavailable):
                get_intent_json("x")

    # ---- retry/backoff helper & path ----
    def test_with_retries_eventual_success(self):
        calls = {"n": 0}
        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("temporary unavailable")
            return "OK"
        from chat.llm import _with_retries
        out = _with_retries(flaky)
        self.assertEqual(out, "OK")
        self.assertEqual(calls["n"], 3)

    def test_with_retries_non_retryable(self):
        from chat.llm import _with_retries
        def bad(): raise RuntimeError("syntax error")
        with self.assertRaises(RuntimeError):
            _with_retries(bad)

    def test_with_retries_retryable_exhausts(self):
        from chat.llm import _with_retries
        def always_retryable(): raise RuntimeError("temporary unavailable")
        with self.assertRaises(RuntimeError):
            _with_retries(always_retryable)

    @patch("chat.llm.time.sleep", return_value=None)
    @patch("chat.llm._get_model")
    def test_get_intent_json_retry_then_success(self, mock_get_model, _sleep):
        import chat.llm as llm
        model = Mock()
        side_effects = [
            RuntimeError("temporary unavailable"),
            RuntimeError("deadline exceeded"),
            self._mk_resp(text='{"intent":"TOTAL_PATIENTS","args":{}}'),
        ]
        def _gen(*_a, **_k):
            e = side_effects.pop(0)
            if isinstance(e, Exception):
                raise e
            return e
        model.generate_content.side_effect = _gen
        mock_get_model.return_value = model
        out = llm.get_intent_json("berapa total pasien?")
        self.assertEqual(out, '{"intent":"TOTAL_PATIENTS","args":{}}')

    # ---- JSON helper coverage ----
    def test_strip_to_json_line_and_try_parse_repairs(self):
        from chat.llm import _strip_to_json_line, _try_parse_json
        s = """```json
        { 'a': 1, 'b': [2,3,], }
        ``` trailing stuff
        """
        line = _strip_to_json_line(s)
        self.assertTrue(line.startswith("{") and line.endswith("}"))
        obj = _try_parse_json(s)
        self.assertEqual(obj, {"a": 1, "b": [2, 3]})

    def test_try_parse_json_none_on_garbage_and_early_empty(self):
        from chat.llm import _try_parse_json
        self.assertIsNone(_try_parse_json("just words"))
        self.assertIsNone(_try_parse_json(""))
        self.assertIsNone(_try_parse_json("   \n\t"))

    # ---- _extract_text paths ----
    def test_extract_text_fallback_to_resp_text(self):
        from chat.llm import _extract_text
        resp = NS(candidates=[], prompt_feedback=None, text="fallback text")
        self.assertEqual(_extract_text(resp), "fallback text")

    def test_extract_text_exception_then_fallback(self):
        from chat.llm import _extract_text
        resp = NS(candidates=object(), prompt_feedback=None, text="from-text-fallback")
        self.assertEqual(_extract_text(resp), "from-text-fallback")

    # ---- ask_gemini_text paths ----
    @patch("chat.llm._get_model")
    def test_ask_gemini_text_uses_resp_text(self, mock_get_model):
        from chat.llm import ask_gemini_text
        model = Mock()
        model.generate_content.return_value = NS(candidates=[], prompt_feedback=None, text="answer-via-text")
        mock_get_model.return_value = model
        self.assertEqual(ask_gemini_text("hi"), "answer-via-text")

    # ---- retryable keyword classifier ----
    def test_is_retryable_error_keywords(self):
        from chat.llm import _is_retryable_error
        self.assertTrue(_is_retryable_error(RuntimeError("deadline exceeded")))
        self.assertTrue(_is_retryable_error(RuntimeError("429")))
        self.assertTrue(_is_retryable_error(RuntimeError("temporary failure")))
        self.assertTrue(_is_retryable_error(RuntimeError("transport error")))
        self.assertTrue(_is_retryable_error(RuntimeError("connection reset by peer")))
        self.assertTrue(_is_retryable_error(RuntimeError("internal server error")))
        self.assertFalse(_is_retryable_error(RuntimeError("syntax error in prompt")))

    # ---- fastpath_intent branches ----
    def test_fastpath_intent(self):
        from chat.llm import _fastpath_intent
        self.assertIn('"UNSUPPORTED"', _fastpath_intent("hi"))
        self.assertIn('"UNSUPPORTED"', _fastpath_intent("  "))
        self.assertIn('"UNSUPPORTED"', _fastpath_intent("hi there"))  # two words
        self.assertIsNone(_fastpath_intent("how many patients do we have today?"))

    # ---- _get_model branches ----
    @patch("chat.llm.genai")
    def test_get_model_cached(self, _mock_genai):
        import chat.llm as llm
        sentinel = object()
        llm._model = sentinel
        self.assertIs(llm._get_model(), sentinel)

    def test_get_model_missing_key(self):
        import chat.llm as llm
        with patch.object(llm, "settings", NS(GEMINI_API_KEY=None, GEMINI_MODEL=None)):
            with self.assertRaises(llm.GeminiConfigError):
                llm._get_model()

    @patch("chat.llm.genai.GenerativeModel", side_effect=Exception("boom"))
    def test_get_model_config_error(self, _gm):
        import chat.llm as llm
        with patch.object(llm, "settings", NS(GEMINI_API_KEY="abc", GEMINI_MODEL=None)):
            with self.assertRaises(llm.GeminiConfigError):
                llm._get_model()
    # ---- _get_model: happy path sets cache then returns (hits `_model = _m` and `return _model`) ----
    def test_get_model_success_sets_and_returns(self):
        import chat.llm as llm
        llm._model = None
        with patch.object(llm, "settings", NS(GEMINI_API_KEY="abc", GEMINI_MODEL=None)), \
             patch("chat.llm.genai.configure") as mock_cfg, \
             patch("chat.llm.genai.GenerativeModel") as mock_gm:
            sentinel = object()
            mock_gm.return_value = sentinel
            out = llm._get_model()
            self.assertIs(out, sentinel)      # ensures we hit `return _model`
            self.assertIs(llm._model, sentinel)  # ensures we hit `_model = _m`
            mock_cfg.assert_called_once()

    # ---- ask_gemini_text: app timeout guard (hits `except FUTimeout:` block) ----
    def test_ask_gemini_text_app_timeout_maps(self):
        class _FakeFuture:
            def result(self, timeout=None):
                from concurrent.futures import TimeoutError as FUTimeout
                raise FUTimeout()

        class _FakeExecutor:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def submit(self, fn): return _FakeFuture()

        with patch("chat.llm._get_model") as gm, \
             patch("chat.llm.ThreadPoolExecutor", return_value=_FakeExecutor()):
            gm.return_value = Mock()  # model object (unused due to timeout)
            from chat.llm import ask_gemini_text, GeminiUnavailable
            with self.assertRaises(GeminiUnavailable):
                ask_gemini_text("hi")
# =========================
# Repo extra coverage
# =========================
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

# =========================
# Sqlgen extra coverage
# =========================
class SqlGenMoreTests(SimpleTestCase):
    def test_ensure_limit_no_append_if_present(self):
        from chat.sqlgen import _ensure_limit
        sql = "SELECT * FROM patients LIMIT 5;"
        self.assertEqual(_ensure_limit(sql), sql)  # unchanged

    def test_ensure_limit_adds_when_missing_and_strips_semicolon(self):
        from chat.sqlgen import _ensure_limit
        sql = "SELECT id FROM patients;"
        out = _ensure_limit(sql, default_limit=123)
        self.assertTrue(out.lower().startswith("select id from patients"))
        self.assertTrue(out.rstrip().endswith("LIMIT 123;"))

    def test_ensure_select_only_salvage_multiline(self):
        from chat.sqlgen import _ensure_select_only
        blob = """
Here is your SQL:
SELECT id, name FROM patients WHERE age > 30
-- end
"""
        out = _ensure_select_only(blob)
        self.assertEqual(out.strip(), "SELECT id, name FROM patients WHERE age > 30")

    def test_safe_select_with_leading_whitespace(self):
        from chat.sqlgen import _ensure_select_only
        out = _ensure_select_only("   SELECT 1")
        self.assertEqual(out, "SELECT 1")

    @patch("chat.sqlgen.ask_gemini_text", return_value="SELECT sin FROM patients")
    def test_generate_semantic_sql_no_auto_limit(self, _mock_llm):
        from chat.sqlgen import generate_semantic_sql
        sql = generate_semantic_sql("list sin", add_default_limit=False)
        self.assertRegex(sql, r"(?is)^select\s+(\w+\.)?sin\s+from\s+patients(\s+\w+)?\s*;?$")


    @patch("chat.sqlgen.ask_gemini_text", return_value="SELECT sin FROM patients")
    def test_generate_semantic_sql_with_auto_limit(self, _mock_llm):
        from chat.sqlgen import generate_semantic_sql
        sql = generate_semantic_sql("list sin", add_default_limit=True)
        self.assertRegex(sql, r"(?is)^select\s+(\w+\.)?sin\s+from\s+patients(\s+\w+)?\s+limit\s+\d+;?$")

# =========================
# Views helper coverage (unit-level)
# =========================
class ViewsHelpersTests(SimpleTestCase):
    def test_get_or_create_demo_user_id_from_cookie_ok_and_bad(self):
        from chat import views as v
        req = NS(COOKIES={v.DEMO_COOKIE_NAME: "11111111-1111-1111-1111-111111111111"})
        self.assertEqual(
            str(v._get_or_create_demo_user_id(req)),
            "11111111-1111-1111-1111-111111111111"
        )
        # bad/garbled value returns None
        req_bad = NS(COOKIES={v.DEMO_COOKIE_NAME: "not-a-uuid"})
        self.assertIsNone(v._get_or_create_demo_user_id(req_bad))

    def test_attach_demo_cookie_skips_when_authenticated(self):
        from chat import views as v
        class Resp: 
            def __init__(self): self.cookies = {}
            def set_cookie(self, k, val, **kw): self.cookies[k] = (val, kw)
        # authenticated user -> no cookie set
        req = NS(user=NS(is_authenticated=True))
        resp = Resp()
        v._attach_demo_cookie_if_needed(req, resp, uuid.uuid4())
        self.assertEqual(resp.cookies, {})

    def test_attach_demo_cookie_sets_when_anonymous(self):
        from chat import views as v
        class Resp: 
            def __init__(self): self.cookies = {}
            def set_cookie(self, k, val, **kw): self.cookies[k] = (val, kw)
        req = NS(user=NS(is_authenticated=False))
        resp = Resp()
        fake = uuid.UUID("22222222-2222-2222-2222-222222222222")
        v._attach_demo_cookie_if_needed(req, resp, fake)
        self.assertIn(v.DEMO_COOKIE_NAME, resp.cookies)
        self.assertEqual(resp.cookies[v.DEMO_COOKIE_NAME][0], str(fake))

    def test_current_user_id_authenticated_uuid_and_non_uuid(self):
        from chat import views as v
        # valid UUID pk
        req1 = NS(user=NS(is_authenticated=True, pk="33333333-3333-3333-3333-333333333333"))
        self.assertEqual(
            str(v._current_user_id(req1)),
            "33333333-3333-3333-3333-333333333333"
        )
        # non-UUID pk -> deterministic uuid5
        req2 = NS(user=NS(is_authenticated=True, pk=123))
        out = v._current_user_id(req2)
        self.assertIsInstance(out, uuid.UUID)

    def test_current_user_id_demo_cookie_fallback_and_random(self):
        from chat import views as v
        # has demo cookie
        req1 = NS(user=NS(is_authenticated=False), COOKIES={v.DEMO_COOKIE_NAME: "44444444-4444-4444-4444-444444444444"})
        self.assertEqual(
            str(v._current_user_id(req1)),
            "44444444-4444-4444-4444-444444444444"
        )
        # no cookie -> random uuid
        req2 = NS(user=NS(is_authenticated=False), COOKIES={})
        self.assertIsInstance(v._current_user_id(req2), uuid.UUID)

    def test_first_words_markdown_strip_and_ellipsis(self):
        from chat import views as v
        s = "**Hello**  _world_  `code` ##title > quote"
        self.assertEqual(v._first_words(s, 2), "Hello world")
        long = "word " * 200
        out = v._first_words(long, 200)
        self.assertTrue(out.endswith("…"))  # ellipsis when over length

    def test_payload_paths_data_json_form_query_and_bad_json(self):
        from chat import views as v

        # 1) DRF-like request.data (already parsed)
        req1 = NS(data={"a": ["x", "y"], "b": "z"})
        self.assertEqual(v._payload(req1), {"a": "x", "b": "z"})  # flattens list

        # 2) Raw JSON body branch (request.data absent/falsey)
        raw = json.dumps({"u": ["p", "q"], "v": 1})
        req2 = NS(data=None, body=raw.encode(), POST=None, GET=None)
        self.assertEqual(v._payload(req2), {"u": "p", "v": 1})

        # 3) Bad JSON falls through to GET/POST
        req3 = NS(
            data=None,
            body=b"{not json}",
            POST=NS(dict=lambda: {"f": ["one", "two"], "g": "h"}),
            GET=NS(dict=lambda: {}),
        )
        self.assertEqual(v._payload(req3), {"f": "one", "g": "h"})

        # 4) No data anywhere -> {}
        req4 = NS(data=None, body=b"", POST=NS(dict=lambda: {}), GET=NS(dict=lambda: {}))
        self.assertEqual(v._payload(req4), {})

# =========================
# Views API extra coverage (cookie + error paths)
# =========================
class ViewsApiMoreTests(APITestCase):
    def setUp(self):
        from authentication.models import User
        from django.contrib.auth.hashers import make_password
        self.user = User.objects.create(
            username="vuser",
            password=make_password("pw"),
            display_name="vuser",
            email="vuser@example.com",
            roles=["researcher"],
            is_verified=True,
        )
        # Anonymous requests (no force_authenticate) to exercise demo cookie paths.

    def test_sessions_get_sets_demo_cookie_when_anonymous(self):
        r = self.client.get(reverse("chat:sessions"))
        self.assertEqual(r.status_code, 200)
        # Robust: check the cookie object directly
        self.assertIn("demo_user_id", r.cookies)

    def test_sessions_post_sets_cookie_and_returns_id(self):
        r = self.client.post(reverse("chat:sessions"), {}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertIn("id", r.json())
        self.assertIn("demo_user_id", r.cookies)

    def test_post_message_raw_json_body_path(self):
        sid = self.client.post(reverse("chat:sessions"), {}, format="json").json()["id"]
        payload = json.dumps({"content": "Hello from raw"})
        r = self.client.post(
            reverse("chat:post_message", args=[sid]),
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)


    @patch("chat.views.answer_question", side_effect=Exception("boom"))
    @patch("chat.views.settings")
    def test_ask_exception_debug_true_returns_demo_answer_and_cookie(self, mock_settings, _mock_answer):
        mock_settings.DEBUG = True
        sid = self.client.post(reverse("chat:sessions"), {}, format="json").json()["id"]
        r = self.client.post(reverse("chat:ask", args=[sid]), {"q": "bad?"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("answer", r.json())
        self.assertIn("demo_user_id", r.cookies)

    @patch("chat.views.answer_question", side_effect=Exception("boom"))
    @patch("chat.views.settings")
    def test_ask_exception_debug_false_returns_502(self, mock_settings, _mock_answer):
        mock_settings.DEBUG = False
        sid = self.client.post(reverse("chat:sessions"), {}, format="json").json()["id"]
        r = self.client.post(reverse("chat:ask", args=[sid]), {"q": "bad?"}, format="json")
        self.assertEqual(r.status_code, 502)



class ViewsPayloadBranches(SimpleTestCase):
    def test_payload_request_data_dict_cast_raises_then_uses_raw_json(self):
        # Simulate request.data present but dict(request.data) raises -> except branch,
        # then raw JSON body is used.
        from chat import views as v

        class BadData:
            # dict(BadData()) raises TypeError
            pass

        raw = json.dumps({"x": ["y"], "z": 1})
        req = NS(
            data=BadData(),          # triggers the try/except
            body=raw.encode(),       # valid raw json fallback
            POST=NS(dict=lambda: {}),
            GET=NS(dict=lambda: {}),
        )
        out = v._payload(req)
        assert out == {"x": "y", "z": 1}

    def test_payload_form_then_query_fallback(self):
        from chat import views as v

        # a) bad JSON -> POST path
        req1 = NS(
            data=None,
            body=b"{not-json}",
            POST=NS(dict=lambda: {"a": ["one"], "b": "two"}),  # truthy -> use POST
            GET=NS(dict=lambda: {"ignored": "x"}),
        )
        out1 = v._payload(req1)
        assert out1 == {"a": "one", "b": "two"}

        # b) bad JSON + empty POST (falsy) -> GET path
        req2 = NS(
            data=None,
            body=b"{bad",
            POST={},  # falsy, so it will skip POST and check GET
            GET=NS(dict=lambda: {"q": ["hello"], "k": "v"}),
        )
        out2 = v._payload(req2)
        assert out2 == {"q": "hello", "k": "v"}

class ViewsAskPrettyJson(APITestCase):
    def setUp(self):
        from authentication.models import User
        from django.contrib.auth.hashers import make_password
        self.user = User.objects.create(
            username="vjson",
            password=make_password("pw"),
            display_name="vjson",
            email="vjson@example.com",
            roles=["researcher"],
            is_verified=True,
        )

    @patch("chat.views.answer_question", return_value={"ok": True, "rows": [1, 2, 3]})
    def test_ask_pretty_prints_dict_and_persists_assistant(self, _mock_answer):
        # Create session
        sid = self.client.post(reverse("chat:sessions"), {}, format="json").json()["id"]

        # Ask with a question; answer_question returns a dict → pretty-printed JSON
        r = self.client.post(reverse("chat:ask", args=[sid]), {"q": "please json"}, format="json")
        self.assertEqual(r.status_code, 200)
        ans = r.json()["answer"]

        # Pretty JSON has newlines/indentation
        self.assertTrue(ans.startswith("{\n"))
        self.assertIn('"ok": true', ans)
        self.assertIn('"rows": [\n', ans)  # indented array

        # Verify an assistant message with that content exists
        msgs = self.client.get(reverse("chat:get_messages", args=[sid])).json()["messages"]
        # last message should be assistant with same pretty JSON
        self.assertGreaterEqual(len(msgs), 2)
        self.assertEqual(msgs[-1]["role"], "assistant")
        self.assertEqual(msgs[-1]["content"], ans)
