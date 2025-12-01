# audittrail/tests/test_audittrail_stubs.py

from types import SimpleNamespace
import json

from django.test import SimpleTestCase, RequestFactory
from django.http import HttpResponse

from audittrail import services
from audittrail.middleware import AuditTrailMiddleware, AUDIT_SESSION_KEY
from audittrail.models import ActivityLog


# ---- Module-level stubs ----

class FakeActivityLogManager:
    def __init__(self):
        self.created = []

    def create(self, **kwargs):
        self.created.append(kwargs)
        # return simple stub row
        return SimpleNamespace(**kwargs)


class FakeActivityLog:
    # shared manager instance
    objects = FakeActivityLogManager()


# ---- Tests for services.log_activity (stubbed model) ----

class TestLogActivityWithStubModel(SimpleTestCase):
    def setUp(self):
        # Save original, then patch
        self._orig_ActivityLog = services.ActivityLog
        services.ActivityLog = FakeActivityLog

        # reset manager between tests
        FakeActivityLog.objects.created.clear()

    def tearDown(self):
        # Restore original
        services.ActivityLog = self._orig_ActivityLog

    def test_log_activity_minimal_arguments_uses_metadata_stub(self):
        result = services.log_activity(
            user=None,
            event_type="FEATURE_USED",
            target=None,
            request=None,
            metadata={"foo": "bar"},
        )

        created_items = FakeActivityLog.objects.created
        self.assertEqual(len(created_items), 1)

        created = created_items[0]
        self.assertEqual(created["event_type"], "FEATURE_USED")
        self.assertEqual(created["metadata"]["foo"], "bar")
        self.assertEqual(created["username"], "")
        self.assertIsNone(created["ip_address"])
        self.assertEqual(created["user_agent"], "")
        self.assertEqual(created["request_id"], "")
        self.assertIsInstance(result, SimpleNamespace)

    def test_log_activity_populates_target_fields_from_model_stub(self):
        class DummyTarget:
            pk = 123

            def __str__(self):
                return "DummyTarget#123"

            class _meta:
                app_label = "myapp"
                model_name = "dummy"

        result = services.log_activity(
            user=None,
            event_type="ANNOTATION_UPDATED",
            target=DummyTarget(),
            request=None,
            metadata={},
        )

        created = FakeActivityLog.objects.created[-1]

        self.assertEqual(created["target_app"], "myapp")
        self.assertEqual(created["target_model"], "dummy")
        self.assertEqual(created["target_id"], "123")
        self.assertEqual(created["target_repr"], "DummyTarget#123")
        self.assertEqual(result.event_type, "ANNOTATION_UPDATED")

    def test_log_activity_prefers_metadata_username_when_user_missing(self):
        result = services.log_activity(
            user=None,
            event_type="USER_LOGIN",
            target=None,
            request=None,
            metadata={"username": "stubuser"},
        )

        created = FakeActivityLog.objects.created[-1]
        self.assertEqual(created["username"], "stubuser")
        self.assertEqual(created["metadata"]["username"], "stubuser")
        self.assertEqual(result.username, "stubuser")


# ---- Tests for AuditTrailMiddleware (stubbed log_activity) ----

class TestAuditTrailMiddlewareWithStubLogger(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

        from audittrail import middleware
        self.middleware_module = middleware

        # Save original log_activity
        self._orig_log_activity = middleware.log_activity
        self.logged_calls = []

        def stub_log_activity(**kwargs):
            self.logged_calls.append(kwargs)
            return SimpleNamespace(**kwargs)

        # Patch with stub
        self.middleware_module.log_activity = stub_log_activity

        # middleware needs a get_response
        self.middleware = AuditTrailMiddleware(get_response=lambda r: HttpResponse("ok"))

    def tearDown(self):
        # Restore original log_activity
        self.middleware_module.log_activity = self._orig_log_activity

    def _run_through_middleware(self, request):
        def dummy_view(req, *args, **kwargs):
            return HttpResponse("ok")

        self.middleware.process_view(request, dummy_view, (), {})
        response = HttpResponse("ok", status=200)
        return self.middleware.process_response(request, response)

    def test_login_request_logs_username_from_payload_stub(self):
        body = {"username": "alice"}
        req = self.rf.post(
            "/auth/login/",
            data=json.dumps(body),
            content_type="application/json",
        )
        req.user = SimpleNamespace(is_authenticated=False)

        class DummySession(dict):
            pass

        req.session = DummySession()

        self._run_through_middleware(req)

        self.assertEqual(len(self.logged_calls), 1)
        log_kwargs = self.logged_calls[0]

        self.assertEqual(log_kwargs["event_type"], ActivityLog.EventType.USER_LOGIN)
        self.assertEqual(log_kwargs["metadata"]["username"], "alice")
        self.assertEqual(log_kwargs["metadata"]["path"], "/auth/login/")
        self.assertEqual(log_kwargs["metadata"]["method"], "POST")
        self.assertIsNone(log_kwargs["user"])
        self.assertEqual(req.session.get(AUDIT_SESSION_KEY), "alice")

    def test_ocr_upload_uses_session_username_stub(self):
        """
        For OCR:
        - process_view computes audit_username from session/last-known/anonymous
        - process_response uses that as precomputed_username fallback.
        Here we simulate a username already in the session.
        """
        req = self.rf.post("/ocr/", data=b"", content_type="application/octet-stream")
        req.user = SimpleNamespace(is_authenticated=False)

        class DummySession(dict):
            pass

        req.session = DummySession()
        # simulate that a previous login already stored username in session
        req.session[AUDIT_SESSION_KEY] = "precomputed-stub-user"

        self._run_through_middleware(req)

        self.assertEqual(len(self.logged_calls), 1)
        log_kwargs = self.logged_calls[0]

        self.assertEqual(log_kwargs["event_type"], ActivityLog.EventType.OCR_UPLOADED)
        # username should come from session
        self.assertEqual(log_kwargs["metadata"]["username"], "precomputed-stub-user")
        self.assertEqual(req.session.get(AUDIT_SESSION_KEY), "precomputed-stub-user")

    def test_authenticated_feature_request_logs_real_username_stub(self):
        req = self.rf.get("/api/chat/")
        req.user = SimpleNamespace(is_authenticated=True, username="hafizh")

        class DummySession(dict):
            pass

        req.session = DummySession()

        self._run_through_middleware(req)

        self.assertEqual(len(self.logged_calls), 1)
        log_kwargs = self.logged_calls[0]

        self.assertEqual(log_kwargs["event_type"], ActivityLog.EventType.FEATURE_USED)
        self.assertEqual(log_kwargs["metadata"]["username"], "hafizh")
        self.assertEqual(log_kwargs["user"].username, "hafizh")
        self.assertEqual(req.session.get(AUDIT_SESSION_KEY), "hafizh")
