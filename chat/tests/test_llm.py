from unittest.mock import patch, Mock
from types import SimpleNamespace as NS
import json
from django.test import SimpleTestCase
from rest_framework.test import APITestCase

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

class ViewsGuardrailsIntegrationTests(APITestCase):
    def setUp(self):
        from authentication.models import User
        from django.contrib.auth.hashers import make_password

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

import time
from django.test import SimpleTestCase, override_settings

from chat import llm
from chat.llm import (
    GeminiError,
    GeminiBlocked,
    GeminiUnavailable,
    GeminiConfigError,
    ResilientCaller,
    IntentJsonNormalizer,
    IntentExtractor,
)


# ---------- Helpers for fake responses ----------

class FakePart:
    def __init__(self, text: str):
        self.text = text


class FakeContent:
    def __init__(self, parts):
        self.parts = parts


class FakeCandidate:
    def __init__(self, text=None, finish_reason=None):
        self.content = FakeContent([FakePart(text)]) if text is not None else None
        self.finish_reason = finish_reason


class FakeResp:
    def __init__(self, text=None, candidates=None, block_reason=None):
        self.text = text
        self.candidates = candidates
        if block_reason:
            self.prompt_feedback = Mock(block_reason=block_reason)
        else:
            self.prompt_feedback = None


# ---------- Low-level utils ----------

class StripToJsonTests(SimpleTestCase):
    def test_strip_to_json_line_basic(self):
        s = """```json
        { "intent": "TOTAL_PATIENTS", "args": {} }
        ```"""
        out = llm._strip_to_json_line(s)
        self.assertEqual(out, '{"intent":"TOTAL_PATIENTS","args":{}}'.replace(" ", ""))


class ExtractTextTests(SimpleTestCase):
    def test_extract_from_candidates(self):
        resp = FakeResp(candidates=[FakeCandidate(text=" hello ")])
        self.assertEqual(llm._extract_text(resp), "hello")

    def test_extract_from_text_fallback(self):
        resp = FakeResp(text=" raw text ")
        self.assertEqual(llm._extract_text(resp), "raw text")


class RetryableErrorTests(SimpleTestCase):
    def test_retryable_true(self):
        self.assertTrue(llm._is_retryable_error(Exception("timeout")))
        self.assertTrue(llm._is_retryable_error(Exception("429 Too Many Requests")))

    def test_retryable_false(self):
        self.assertFalse(llm._is_retryable_error(Exception("some other error")))


class WithRetriesTests(SimpleTestCase):
    def test_with_retries_eventual_success(self):
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            if calls["n"] < 2:
                raise Exception("timeout")  # retryable
            return "ok"

        with patch("time.sleep", return_value=None):
            out = llm._with_retries(fn)
        self.assertEqual(out, "ok")
        self.assertEqual(calls["n"], 2)

    def test_with_retries_non_retryable_raises(self):
        def fn():
            raise ValueError("nope")

        with self.assertRaises(ValueError):
            llm._with_retries(fn)


class TryParseJsonTests(SimpleTestCase):
    def test_try_parse_json_direct(self):
        obj = llm._try_parse_json('{"intent":"X","args":{}}')
        self.assertEqual(obj["intent"], "X")

    def test_try_parse_json_repair(self):
        obj = llm._try_parse_json("{'intent': 'Y', 'args': {},}")
        self.assertEqual(obj["intent"], "Y")

    def test_try_parse_json_fail(self):
        self.assertIsNone(llm._try_parse_json("not json at all"))


class FastpathIntentTests(SimpleTestCase):
    def test_fastpath_empty(self):
        out = llm._fastpath_intent("")
        self.assertEqual(out, json.dumps({"intent": "UNSUPPORTED", "args": {}}))

    def test_fastpath_smalltalk(self):
        out = llm._fastpath_intent("hi")
        self.assertEqual(out, json.dumps({"intent": "UNSUPPORTED", "args": {}}))

    def test_fastpath_none(self):
        out = llm._fastpath_intent("how many patients are there")
        self.assertIsNone(out)


# ---------- ResilientCaller ----------

class ResilientCallerTests(SimpleTestCase):
    def test_run_success(self):
        c = ResilientCaller(app_timeout_s=1)
        out = c.run(lambda: "ok")
        self.assertEqual(out, "ok")

    def test_run_timeout_raises_unavailable(self):
        c = ResilientCaller(app_timeout_s=0.01)

        def slow():
            time.sleep(0.2)
            return "late"

        with self.assertRaises(GeminiUnavailable):
            c.run(slow)


# ---------- GeminiLLMClient ----------

class GeminiLLMClientTests(SimpleTestCase):
    @override_settings(GEMINI_API_KEY="dummy")
    @patch("chat.llm.genai")
    def test_generate_delegates_to_model(self, mock_genai):
        mock_model = Mock()
        mock_genai.GenerativeModel.return_value = mock_model

        client = llm.GeminiLLMClient()
        client.generate(["x"], generation_config={"temperature": 0}, timeout_s=5)

        mock_model.generate_content.assert_called_once()


# ---------- Normalizer ----------

class IntentJsonNormalizerTests(SimpleTestCase):
    def test_parse_valid(self):
        n = IntentJsonNormalizer()
        obj = n.parse('{"intent":"A","args":{}}')
        self.assertEqual(obj["intent"], "A")

    def test_parse_invalid(self):
        n = IntentJsonNormalizer()
        self.assertIsNone(n.parse("not json"))


# ---------- IntentExtractor.infer_intent ----------

class IntentExtractorInferTests(SimpleTestCase):
    def _make_extractor(self, resp):
        fake_llm = Mock()
        fake_llm.generate.return_value = resp
        caller = ResilientCaller(app_timeout_s=1)
        normalizer = IntentJsonNormalizer()
        return IntentExtractor(fake_llm, caller, normalizer)

    def test_infer_success(self):
        resp = FakeResp(candidates=[FakeCandidate(text='{"intent":"TOTAL_PATIENTS","args":{}}')])
        ex = self._make_extractor(resp)
        out = ex.infer_intent("q")
        self.assertEqual(out, {"intent": "TOTAL_PATIENTS", "args": {}})

    def test_infer_blocked_prompt_feedback(self):
        resp = FakeResp(text='{}', block_reason="safety")
        ex = self._make_extractor(resp)
        with self.assertRaises(GeminiBlocked):
            ex.infer_intent("q")

    def test_infer_blocked_finish_reason(self):
        resp = FakeResp()
        resp.candidates = [FakeCandidate(text='{}', finish_reason="safety")]
        ex = self._make_extractor(resp)
        with self.assertRaises(GeminiBlocked):
            ex.infer_intent("q")

    def test_infer_empty_response(self):
        resp = FakeResp(text="   ")
        ex = self._make_extractor(resp)
        with self.assertRaises(GeminiError):
            ex.infer_intent("q")

    def test_infer_invalid_json(self):
        # normalizer will fail to parse
        fake_llm = Mock()
        fake_llm.generate.return_value = FakeResp(candidates=[FakeCandidate(text="not json")])
        caller = ResilientCaller(app_timeout_s=1)
        normalizer = IntentJsonNormalizer()
        ex = IntentExtractor(fake_llm, caller, normalizer)
        with self.assertRaises(GeminiError):
            ex.infer_intent("q")

    def test_infer_bad_schema(self):
        # valid JSON but missing required keys
        fake_llm = Mock()
        fake_llm.generate.return_value = FakeResp(candidates=[FakeCandidate(text='{"x":1}')])
        caller = ResilientCaller(app_timeout_s=1)
        normalizer = IntentJsonNormalizer()
        ex = IntentExtractor(fake_llm, caller, normalizer)
        with self.assertRaises(GeminiError):
            ex.infer_intent("q")


# ---------- IntentExtractor.free_text ----------

class IntentExtractorFreeTextTests(SimpleTestCase):
    def test_free_text_success(self):
        resp = FakeResp(candidates=[FakeCandidate(text="hello")])
        fake_llm = Mock()
        fake_llm.generate.return_value = resp
        ex = IntentExtractor(fake_llm, ResilientCaller(app_timeout_s=1), IntentJsonNormalizer())
        out = ex.free_text("q")
        self.assertEqual(out, "hello")

    def test_free_text_blocked(self):
        resp = FakeResp(text="x", block_reason="safety")
        fake_llm = Mock()
        fake_llm.generate.return_value = resp
        ex = IntentExtractor(fake_llm, ResilientCaller(app_timeout_s=1), IntentJsonNormalizer())
        with self.assertRaises(GeminiBlocked):
            ex.free_text("q")

    def test_free_text_timeout_maps_to_unavailable(self):
        def _boom():
            raise GeminiUnavailable("app_timeout")

        fake_llm = Mock()
        caller = Mock()
        caller.run.side_effect = _boom
        ex = IntentExtractor(fake_llm, caller, IntentJsonNormalizer())

        with self.assertRaises(GeminiUnavailable):
            ex.free_text("q")

    def test_free_text_empty_response(self):
        resp = FakeResp(text="   ")
        fake_llm = Mock()
        fake_llm.generate.return_value = resp
        ex = IntentExtractor(fake_llm, ResilientCaller(app_timeout_s=1), IntentJsonNormalizer())
        with self.assertRaises(GeminiError):
            ex.free_text("q")


# ---------- get_intent_json ----------

class GetIntentJsonTests(SimpleTestCase):
    @override_settings(GEMINI_API_KEY="dummy")
    @patch("chat.llm.IntentExtractor")
    def test_get_intent_json_ok(self, MockExtractor):
        inst = Mock()
        inst.infer_intent.return_value = {"intent": "TOTAL_PATIENTS", "args": {}}
        MockExtractor.return_value = inst

        out = llm.get_intent_json("q")
        self.assertEqual(out, '{"intent":"TOTAL_PATIENTS","args":{}}')


# ---------- ask_gemini_text ----------

class AskGeminiTextTests(SimpleTestCase):
    @override_settings(GEMINI_API_KEY="dummy-key")
    @patch("chat.llm._get_model")
    def test_ask_gemini_text_success(self, mock_get_model):
        # Fake model that returns a valid response
        fake_resp = FakeResp(candidates=[FakeCandidate(text="ok")])
        fake_model = Mock()
        fake_model.generate_content.return_value = fake_resp
        mock_get_model.return_value = fake_model

        out = llm.ask_gemini_text("hello", retry_on_empty=False)
        self.assertEqual(out, "ok")

    @override_settings(GEMINI_API_KEY="dummy-key")
    @patch("chat.llm._get_model")
    def test_ask_gemini_text_blocked(self, mock_get_model):
        fake_resp = FakeResp(text="x", block_reason="safety")
        fake_model = Mock()
        fake_model.generate_content.return_value = fake_resp
        mock_get_model.return_value = fake_model

        with self.assertRaises(GeminiBlocked):
            llm.ask_gemini_text("hello", retry_on_empty=False)

    @override_settings(GEMINI_API_KEY="dummy-key")
    @patch("chat.llm._get_model")
    def test_ask_gemini_text_timeout(self, mock_get_model):
        # Force FUTimeout via patched ThreadPoolExecutor
        fake_model = Mock()

        def gen_content(*args, **kwargs):
            time.sleep(0.2)
            return FakeResp(candidates=[FakeCandidate(text="late")])

        fake_model.generate_content.side_effect = gen_content
        mock_get_model.return_value = fake_model

        # Use tiny timeouts
        with patch.object(llm, "APP_TIMEOUT_S", 0.01), \
             patch.object(llm, "DEFAULT_DEADLINE_S", 0.01):
            with self.assertRaises(GeminiUnavailable):
                llm.ask_gemini_text("hello", retry_on_empty=False)

    @override_settings(GEMINI_API_KEY="dummy-key")
    @patch("chat.llm._get_model")
    def test_ask_gemini_text_empty_then_retry_and_fail(self, mock_get_model):
        # First call: empty, second call: still empty => GeminiError("empty_response")
        fake_model = Mock()
        fake_model.generate_content.return_value = FakeResp(text="   ")
        mock_get_model.return_value = fake_model

        with patch("time.sleep", return_value=None):
            with self.assertRaises(GeminiError):
                llm.ask_gemini_text("hello", retry_on_empty=True)

    @override_settings(GEMINI_API_KEY="dummy-key")
    @patch("chat.llm._get_model")
    def test_ask_gemini_text_transport_error(self, mock_get_model):
        fake_model = Mock()
        fake_model.generate_content.side_effect = RuntimeError("transport error")
        mock_get_model.return_value = fake_model

        with self.assertRaises(GeminiError):
            llm.ask_gemini_text("hello", retry_on_empty=False)


class GetModelTests(SimpleTestCase):
    @override_settings(GEMINI_API_KEY=None)
    def test_get_model_missing_key_raises(self):
        # force reload
        with patch.object(llm, "_model", None):
            with self.assertRaises(GeminiConfigError):
                llm._get_model()
