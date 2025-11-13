from unittest.mock import patch, Mock
from chat import sqlgen
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APITestCase
from authentication.models import User
from django.contrib.auth.hashers import make_password

class GuardrailsTests(SimpleTestCase):
    # Note: These tests mock the internal _get_rails function that returns the LLMRails instance.
    @patch("chat.guardrails._get_rails")
    def test_blocked_input_short_circuits(self, mock_get_rails):
        from chat.guardrails import run_with_guardrails
        
        # Create a mock rails instance
        mock_rails_instance = Mock()
        mock_rails_instance.generate.return_value = {"content": "Blocked by policy."} # Or however NeMo signals a block
        mock_get_rails.return_value = mock_rails_instance

        out = run_with_guardrails("forbidden question", lambda _msg: "SHOULD_NOT_RUN")
        
        # Adjust expectation based on how NeMo returns a block response.
        # If NeMo returns the block message directly via generate, check for that.
        # If your logic intercepts and returns it differently, adjust accordingly.
        # For now, assuming NeMo returns the block message via generate if configured to do so.
        mock_rails_instance.generate.assert_called_once_with(
            messages=[{"role": "user", "content": "forbidden question"}]
        )
        # The exact assertion depends on your NeMo configuration for blocking.
        # If NeMo returns the block message directly:
        # self.assertEqual(out, "Blocked by policy.")
        # If NeMo returns an empty response or standard response and your logic handles the block differently,
        # you might need a different setup or test structure.
        # For this example, let's assume it returns the blocked message via generate
        # and your run_with_guardrails passes it through if it's non-empty.
        # If generate returns an empty string/dict, it should fall back.
        # Let's adjust the mock to simulate a block being handled by NeMo's Colang flow.
        # This is complex and depends heavily on your rails.yaml.
        # A simpler approach for the test might be:
        mock_rails_instance.generate.return_value = "Blocked by policy."
        out = run_with_guardrails("forbidden question", lambda _msg: "SHOULD_NOT_RUN")
        self.assertEqual(out, "Blocked by policy.")

    @patch("chat.guardrails._get_rails")
    def test_allows_and_sanitizes_output(self, mock_get_rails):
        from chat.guardrails import run_with_guardrails
        
        # Mock rails to return a standard response, allowing the fallback path to be tested
        # Or, mock it to return a specific sanitized response if your rails.yaml handles output sanitization.
        # For output sanitization test, let's assume NeMo modifies the response.
        mock_rails_instance = Mock()
        mock_rails_instance.generate.return_value = "Sanitized answer." # NeMo returns this after processing the original answer
        mock_get_rails.return_value = mock_rails_instance

        def _answer_fn(msg: str) -> str:
            return "raw answer from _answer_fn"

        out = run_with_guardrails("normal input", _answer_fn)
        
        # Check if NeMo's generate was called with the original input
        mock_rails_instance.generate.assert_called_once_with(
            messages=[{"role": "user", "content": "normal input"}]
        )
        # Check if the output from NeMo was returned (assuming it sanitized/processed it)
        self.assertEqual(out, "Sanitized answer.")

    @patch("chat.guardrails._get_rails")
    def test_no_sanitized_response_falls_back_to_raw(self, mock_get_rails):
        from chat.guardrails import run_with_guardrails
        
        # Mock rails to return an empty response or a response that doesn't trigger guardrail logic
        # This should cause the function to call the fallback answer_fn
        mock_rails_instance = Mock()
        # NeMo might return an empty string, empty dict, or None-like response if no specific flow matches
        # and no blocking occurs. Let's assume it returns an empty string or a dict without content.
        mock_rails_instance.generate.return_value = "" 
        mock_get_rails.return_value = mock_rails_instance

        def _answer_fn(msg: str) -> str:
            return "fallback answer"

        out = run_with_guardrails("normal input", _answer_fn)
        
        # Check if NeMo's generate was called
        mock_rails_instance.generate.assert_called_once_with(
            messages=[{"role": "user", "content": "normal input"}]
        )
        # Check if the fallback function was used because NeMo didn't provide an override
        self.assertEqual(out, "fallback answer")

        # Reset mock to test another scenario where generate returns a dict without meaningful content
        mock_rails_instance.reset_mock()
        mock_rails_instance.generate.return_value = {"some_other_key": "value"}
        out2 = run_with_guardrails("normal input 2", _answer_fn)
        mock_rails_instance.generate.assert_called_once_with(
            messages=[{"role": "user", "content": "normal input 2"}]
        )
        self.assertEqual(out2, "fallback answer")

class ViewsGuardrailsIntegrationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create(
            username="gruser",
            password=make_password("pw"),
            display_name="gruser",
            email="gruser@example.com",
            roles=["researcher"],
            is_verified=True,
        )
        session = self.client.session
        session["user_id"] = str(self.user.user_id)
        session.save()

    @patch("chat.views.run_with_guardrails", side_effect=lambda q, fn: "guarded-answer")
    def test_ask_uses_guardrails_wrapper(self, mock_run):
        from django.urls import reverse

        # create session
        sid = self.client.post(reverse("chat:sessions"), {}, format="json").json()["id"]

        # call /ask
        r = self.client.post(
            reverse("chat:ask", args=[sid]),
            {"q": "Hello"},
            format="json",
        )

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["answer"], "guarded-answer")
        mock_run.assert_called_once()

class EnsureSelectOnlyTests(TestCase):
    def test_rejects_non_select_without_salvage(self):
        # No DML keyword, no SELECT anywhere -> should trigger the specific ValueError
        bad = "THIS IS NOT SQL\nAND NO SELECT HERE"
        with self.assertRaisesMessage(ValueError, "Autogenerated SQL is not a SELECT statement."):
            sqlgen._ensure_select_only(bad)

    def test_rejects_forbidden_dml(self):
        bad = "DELETE FROM patients WHERE 1=1;"
        with self.assertRaisesMessage(ValueError, "Forbidden SQL detected (DML/DDL)."):
            sqlgen._ensure_select_only(bad)

    def test_salvages_select_from_multiline_output(self):
        mixed = """Here is your query:
        SELECT * FROM patients;
        Thanks!
        """
        out = sqlgen._ensure_select_only(mixed)
        self.assertEqual(out, "SELECT * FROM patients;")

# chat/tests/test_guardrails_full.py

from django.test import SimpleTestCase, override_settings
from unittest.mock import patch, Mock

from chat import guardrails as gr
from chat.llm import GeminiError, GeminiBlocked


class GetConfigDirTests(SimpleTestCase):
    @override_settings(RAILS_CONFIG_DIR="\\tmp\custom_rails")
    def test_get_config_dir_uses_settings(self):
        path = gr._get_config_dir()
        self.assertEqual(str(path), "\\tmp\\custom_rails")

    def test_get_config_dir_default(self):
        # Ensure it falls back to <this_file_dir>/rails if setting missing
        with patch.object(gr.settings, "RAILS_CONFIG_DIR", new=None, create=True):
            path = gr._get_config_dir()
            self.assertTrue(str(path).endswith("chat/rails") or str(path).endswith("chat\\rails"))


class LoadRailsTests(SimpleTestCase):
    def test_load_rails_returns_none_if_library_missing(self):
        with patch.object(gr, "LLMRails", None), patch.object(gr, "RailsConfig", None):
            rails = gr._load_rails()
            self.assertIsNone(rails)

    def test_load_rails_returns_none_if_config_missing(self):
        # Pretend NeMo is available but config dir doesn't exist
        fake_llmrails = object()
        fake_railsconfig = object()

        with patch.object(gr, "LLMRails", fake_llmrails), \
             patch.object(gr, "RailsConfig", fake_railsconfig), \
             patch.object(gr, "CONFIG_DIR") as cfg:
            cfg.exists.return_value = False
            rails = gr._load_rails()
            self.assertIsNone(rails)

    def test_load_rails_success(self):
        class DummyRails:
            def __init__(self, cfg):
                self.cfg = cfg

        class DummyCfg:
            @staticmethod
            def from_path(p):
                return f"cfg:{p}"

        with patch.object(gr, "LLMRails", DummyRails), \
             patch.object(gr, "RailsConfig", DummyCfg), \
             patch.object(gr, "CONFIG_DIR") as cfg:
            cfg.exists.return_value = True
            rails = gr._load_rails()
            # Should be a DummyRails instance
            self.assertIsInstance(rails, DummyRails)


class GetRailsTests(SimpleTestCase):
    def test_get_rails_returns_global_instance(self):
        with patch.object(gr, "_rails_instance", "SENTINEL"):
            self.assertEqual(gr._get_rails(), "SENTINEL")


class IsOutOfScopeTests(SimpleTestCase):
    def test_out_of_scope_true(self):
        self.assertTrue(gr._is_out_of_scope("What is the meaning of life?"))

    def test_out_of_scope_false(self):
        self.assertFalse(gr._is_out_of_scope("how many patients are there"))


class ExtractTextTests(SimpleTestCase):
    def test_extract_none(self):
        self.assertEqual(gr._extract_text(None), "")

    def test_extract_string(self):
        self.assertEqual(gr._extract_text(" hello "), "hello")

    def test_extract_dict_content(self):
        self.assertEqual(gr._extract_text({"content": " hi "}), "hi")

    def test_extract_dict_messages(self):
        result = gr._extract_text({
            "messages": [
                {"role": "user", "content": "x"},
                {"role": "assistant", "content": " ok "}
            ]
        })
        self.assertEqual(result, "ok")

    def test_extract_dict_unknown_shape_returns_empty(self):
        self.assertEqual(gr._extract_text({"some_other_key": "value"}), "")

    def test_extract_list_messages(self):
        result = gr._extract_text([
            {"role": "user", "content": "x"},
            {"role": "assistant", "content": " hey "}
        ])
        self.assertEqual(result, "hey")

    def test_extract_weird_type(self):
        class Weird:
            pass
        self.assertEqual(gr._extract_text(Weird()), "")


class SafeBackendCallTests(SimpleTestCase):
    def test_safe_backend_ok(self):
        def fb(msg):
            return f"ok:{msg}"
        out = gr._safe_backend_call(fb, "hello")
        self.assertEqual(out, "ok:hello")

    def test_safe_backend_gemini_blocked(self):
        def fb(_):
            raise GeminiBlocked("blocked")
        out = gr._safe_backend_call(fb, "x")
        self.assertIn("Mohon tanyakan pertanyaan yang relevan", out)

    def test_safe_backend_gemini_error(self):
        def fb(_):
            raise GeminiError("empty_response")
        out = gr._safe_backend_call(fb, "x")
        self.assertIn("Maaf, sistem tidak dapat menjawab", out)

    def test_safe_backend_generic_exception(self):
        def fb(_):
            raise RuntimeError("boom")
        out = gr._safe_backend_call(fb, "x")
        self.assertIn("Maaf, terjadi masalah", out)


class RunWithGuardrailsTests(SimpleTestCase):
    def test_empty_input(self):
        out = gr.run_with_guardrails("", lambda m: f"fb:{m}")
        self.assertEqual(out, "Silakan ajukan pertanyaan terkait data klinis.")

    def test_out_of_scope_short_circuits(self):
        called = {"fb": False}

        def fb(_):
            called["fb"] = True
            return "fb"

        out = gr.run_with_guardrails("what is the meaning of life", fb)
        self.assertEqual(out, "Mohon tanyakan pertanyaan yang relevan dengan data klinis.")
        self.assertFalse(called["fb"])

    def test_no_rails_uses_backend(self):
        def fb(msg):
            return f"BACK:{msg}"

        with patch.object(gr, "_get_rails", return_value=None):
            out = gr.run_with_guardrails("how many patients", fb)
        self.assertEqual(out, "BACK:how many patients")

    def test_rails_out_of_scope_message_passthrough(self):
        class DummyRails:
            def generate(self, messages):
                return {"content": "Mohon tanyakan pertanyaan yang relevan dengan data klinis."}

        def fb(_):
            return "fallback-should-not-be-called"

        with patch.object(gr, "_get_rails", return_value=DummyRails()):
            out = gr.run_with_guardrails("x", fb)
        self.assertEqual(out, "Mohon tanyakan pertanyaan yang relevan dengan data klinis.")

    def test_rails_defer_to_backend(self):
        class DummyRails:
            def generate(self, messages):
                return {"content": "__DEFER_TO_BACKEND__"}

        def fb(_):
            return "fallback answer"

        with patch.object(gr, "_get_rails", return_value=DummyRails()):
            out = gr.run_with_guardrails("x", fb)
        self.assertEqual(out, "fallback answer")

    def test_rails_blank_triggers_backend(self):
        class DummyRails:
            def generate(self, messages):
                return {"content": "   "}

        def fb(_):
            return "fallback blank"

        with patch.object(gr, "_get_rails", return_value=DummyRails()):
            out = gr.run_with_guardrails("x", fb)
        self.assertEqual(out, "fallback blank")

    def test_rails_error_message_triggers_backend(self):
        class DummyRails:
            def generate(self, messages):
                return {"content": "I encountered an error processing your request."}

        def fb(_):
            return "fallback error"

        with patch.object(gr, "_get_rails", return_value=DummyRails()):
            out = gr.run_with_guardrails("x", fb)
        self.assertEqual(out, "fallback error")

    def test_rails_sanitized_text_used_directly(self):
        class DummyRails:
            def generate(self, messages):
                return {"content": "sanitized answer"}

        def fb(_):
            return "fb"

        with patch.object(gr, "_get_rails", return_value=DummyRails()):
            out = gr.run_with_guardrails("x", fb)
        self.assertEqual(out, "sanitized answer")

    def test_rails_generate_exception_falls_back(self):
        class DummyRails:
            def generate(self, messages):
                raise RuntimeError("boom")

        def fb(_):
            return "fallback after exception"

        with patch.object(gr, "_get_rails", return_value=DummyRails()):
            out = gr.run_with_guardrails("x", fb)
        self.assertEqual(out, "fallback after exception")
