from unittest.mock import patch
from django.test import SimpleTestCase

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