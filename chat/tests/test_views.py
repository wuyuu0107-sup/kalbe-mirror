from unittest.mock import patch, Mock, MagicMock
from types import SimpleNamespace as NS
import os
import sys
import uuid
import json

from authentication.models import User
from django.urls import reverse
from django.test import SimpleTestCase, Client
from rest_framework.test import APITestCase
from django.contrib.auth.hashers import make_password

from chat.models import ChatSession

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

    @patch("chat.service.answer_question") # Mock the function that generates the answer
    def test_add_messages_and_fetch_history_in_order(self, mock_answer_question):
        # Correct the expected answer to match the test's expectation
        expected_answer = "Hello! How can I assist you today?"
        mock_answer_question.return_value = expected_answer # Mock the service function to return the expected answer

        client = Client() # Or self.client if inheriting from APITestCase
        # 1. Create session - this should return 201
        session_response = client.post(reverse("chat:create_session"))
        self.assertEqual(session_response.status_code, 201, f"Session creation failed: {session_response.content}")
        s_data = session_response.json()
        session_id = s_data["id"]
        print(f"Created session: {session_id}") # Debug: Confirm session ID

        # 2. Send message to the ask endpoint - try using APIClient's format='json'
        # Use 'sid' as the keyword argument name, matching the URL pattern
        # Use DRF's format='json' which should handle serialization and content-type
        r = client.post(
            reverse("chat:ask", kwargs={"sid": session_id}), # Use the correct URL arg name
            data={"text": "Hai"},                          # Send as a dict
            format='json'                                  # Use DRF's JSON handling
        )
        # Debug: Print the response content if it's not 200
        print(f"Ask response status: {r.status_code}, content: {r.content.decode()}")
        self.assertEqual(r.status_code, 200) # Should now pass
        self.assertEqual(r.json().get("answer"), expected_answer)

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



class ViewsPayloadBranches(SimpleTestCase):
    def test_payload_request_data_dict_cast_raises_then_uses_raw_json(self):
        # Simulate request.data present but dict(request.data) raises -> except branch,
        # then raw JSON body is used.
        from chat import views as v
        class BadData:
            # dict(BadData()) raises TypeError
            pass
        raw = json.dumps({"x": ["y"], "z": 1})
        req = MagicMock() # Using MagicMock for req object
        req.data = BadData()          # triggers the try/except
        req.body = raw.encode()       # valid raw json fallback
        req.POST = MagicMock()
        req.POST.dict.return_value = {}
        req.GET = MagicMock()
        req.GET.dict.return_value = {}
        out = v._payload(req)
        self.assertEqual(out, {"x": "y", "z": 1})

    def test_payload_form_then_query_fallback(self):
        from chat import views as v
        # a) bad JSON -> POST path
        req1 = MagicMock() # Using MagicMock for req object
        req1.data = None
        req1.body = b"{not-json}"
        req1.POST = MagicMock()
        req1.POST.dict.return_value = {"a": ["one"], "b": "two"}  # truthy -> use POST
        req1.GET = MagicMock()
        req1.GET.dict.return_value = {"ignored": "x"}
        out1 = v._payload(req1)
        self.assertEqual(out1, {"a": "one", "b": "two"})

        # b) bad JSON + empty POST (falsy) -> GET path
        req2 = MagicMock() # Using MagicMock for req object
        req2.data = None
        req2.body = b"{bad"
        req2.POST = {}  # falsy, so it will skip POST and check GET
        req2.GET = MagicMock()
        req2.GET.dict.return_value = {"q": ["hello"], "k": "v"}
        out2 = v._payload(req2)
        self.assertEqual(out2, {"q": "hello", "k": "v"})

class AskDictAnswerFormattingTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create(
            username="dictuser",
            password=make_password("pw"),
            display_name="dictuser",
            email="dictuser@example.com",
            roles=["researcher"],
            is_verified=True,
        )
        session = self.client.session
        session["user_id"] = str(self.user.user_id)
        session.save()

    @patch("chat.views.run_with_guardrails")
    def test_ask_serializes_dict_answer_to_pretty_json(self, mock_guardrails):
        # Force run_with_guardrails to return a dict so we hit the isinstance(answer, dict) branch
        mock_guardrails.return_value = {"key": "value", "number": 123}

        client = Client()

        # Create session via your create_session endpoint
        session_response = client.post(reverse("chat:create_session"))
        self.assertEqual(session_response.status_code, 201)
        session_id = session_response.json()["id"]

        # Call ask with a simple text payload
        r = client.post(
            reverse("chat:ask", kwargs={"sid": session_id}),
            data=json.dumps({"text": "Give me JSON"}),
            content_type="application/json",
        )

        self.assertEqual(r.status_code, 200)

        body = r.json()
        # Should be pretty-printed JSON string from that branch
        expected = json.dumps({"key": "value", "number": 123}, ensure_ascii=False, indent=2)
        self.assertEqual(body["answer"], expected)