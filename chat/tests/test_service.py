from unittest.mock import patch, Mock
import os
import sys

from django.test import SimpleTestCase
from chat import service

class ServiceTests(SimpleTestCase):
    def setUp(self):
        os.environ.setdefault("DATABASE_URL", "postgresql://fake:fake@localhost:5432/testdb")

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

        # When no rows, still returns "(empty)"
        self.assertEqual(_render_table(["a", "b"], []), "(empty)")

        # When rows exceed max_rows, expect Markdown table + ellipsis row
        cols = ["c1", "c2", "c3"]
        rows = [(i, i + 1, i + 2) for i in range(10)]  # 10 rows total
        out = _render_table(cols, rows, max_rows=8)

        # Basic sanity: header & separator are present
        self.assertIn("| c1 | c2 | c3 |", out)
        self.assertIn("| --- | --- | --- |", out)

        # Ellipsis row in Markdown style for the remaining rows
        self.assertIn("| ... | (2 more rows) |", out)


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

        self.assertTrue(out.startswith("Found 12 rows."))  # still true
        # New Markdown "more rows" indicator inside the rendered table
        self.assertIn("| ... | (", out)


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

    @patch("chat.service.DB")
    @patch("chat.service.generate_semantic_sql", return_value="SELECT a,b,c")
    def test_group_summary_fallback_for_non_2_col(self, _gen, mock_db_cls):
        """
        When there are not exactly 2 columns, _group_summary should not be used.
        We should fall back to the generic table formatting branches.
        """
        mock_db = mock_db_cls.return_value
        mock_db.query.return_value = {
            "columns": ["a", "b", "c"],           # len(cols) = 3 -> not the 2-col path
            "rows": [(1, 2, 3), (4, 5, 6)],
        }

        from chat.service import answer_question
        out = answer_question("show groups")

        # For 2 < len(cols) <= 5, answer_question uses:
        #   "Found {len(rows)} rows.\n\n{_render_table(...)}"
        self.assertTrue(
            out.startswith("Found "),
            msg=f"Unexpected fallback output: {out!r}",
        )

class AnswerQuestionBranchTests(SimpleTestCase):
    def test_answer_question_empty_returns_clinical_prompt(self):
        out = service.answer_question("")
        self.assertEqual(
            out,
            "Silakan ajukan pertanyaan terkait data klinis."
        )

    def test_answer_question_greeting_returns_halo_message(self):
        out = service.answer_question("hai")
        self.assertEqual(
            out,
            "Halo! 👋 Aku asisten yang fokus pada data klinis. "
            "Silakan tanyakan hal yang berkaitan dengan uji klinis atau dataset pasien."
        )



class GroupSummaryCoverageTests(SimpleTestCase):
    def test_group_summary_two_cols_error_falls_back_to_groups(self):
        f = service.DefaultAnswerFormatter()
        cols = ["G", "Val"]
        rows = [("A", "x"), ("B", "y")]  # float() fails for both

        out = f._group_summary("most", cols, rows)

        # Hits the except branch: "Found {len(rows)} groups."
        self.assertIn("Found 2 groups.", out)
        self.assertIn("G | Val", out)

    def test_group_summary_non_two_cols_triggers_final_return(self):
        f = service.DefaultAnswerFormatter()
        cols = ["G", "Val", "Extra"]      # len != 2
        rows = [("A", 1, 2), ("B", 3, 4)]

        out = f._group_summary("anything", cols, rows)

        # This *must* hit the bottom:
        # return f"Found {len(rows)} rows.\n\n{_render_table(cols, rows)}"
        self.assertIn("Found 2 rows.", out)
        self.assertIn("G | Val | Extra", out)
