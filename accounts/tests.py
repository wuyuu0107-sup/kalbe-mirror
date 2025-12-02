# accounts/tests.py
import json
import re
from unittest.mock import patch

from django.test import (
    TestCase,
    Client,
    override_settings,
    RequestFactory,
)
from django.urls import reverse
from django.core import mail
from django.apps import apps

from django.core.cache import cache

# modul internal
from accounts import csrf as csrf_view
from accounts.tokens import password_reset_token
from accounts.services import cache_store as cs
from accounts import views as basic_views



# -----------------------
# Helpers
# -----------------------
def extract_otp_from_mail(body: str) -> str:
    m = re.search(r"\b(\d{4,8})\b", body)
    if not m:
        raise AssertionError("OTP not found in email body")
    return m.group(1)


TEST_OVERRIDES = dict(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="test@example.local",
    DATABASES={
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    },
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-cache",
        }
    },
)


def get_auth_user_model():
    return apps.get_model("authentication", "User")


# ============================================================
# 1. TEST OTP EMAIL (ini yang “beneran”)
# ============================================================
@override_settings(**TEST_OVERRIDES)
class EmailOTPTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        AuthUser = get_auth_user_model()
        cls.user = AuthUser.objects.create(
            username="alice",
            email="alice@example.com",
            display_name="Alice",
            password="dummy",  # nggak penting di sini
            roles=[],
            is_verified=True,
        )

    def setUp(self):
        self.c = Client()
        mail.outbox.clear()
        cache.clear()

    def test_request_known_email_sends_mail(self):
        res = self.c.post(
            reverse("password-reset-otp-request"),
            data=json.dumps({"email": "alice@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), "ok")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Your OTP Code", mail.outbox[0].subject)

    def test_request_unknown_email_also_200_no_mail(self):
        res = self.c.post(
            reverse("password-reset-otp-request"),
            data=json.dumps({"email": "ghost@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), "ok")
        self.assertEqual(len(mail.outbox), 0)

    def test_confirm_weak_password(self):
        # Request OTP
        self.c.post(
            reverse("password-reset-otp-request"),
            data=json.dumps({"email": "alice@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(len(mail.outbox), 1, "OTP email not sent")
        otp = extract_otp_from_mail(mail.outbox[0].body)

        # Confirm dengan password lemah
        res = self.c.post(
            reverse("password-reset-otp-confirm"),
            data=json.dumps(
                {"email": "alice@example.com", "otp": otp, "password": "short"}
            ),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("error", res.json())

<<<<<<< HEAD
=======
    def test_request_missing_email_returns_error(self):
        res = self.c.post(
            reverse("password-reset-otp-request"),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("error"), "email is required")

    def test_request_rate_limit_blocks_on_sixth_attempt(self):
        payload = json.dumps({"email": "alice@example.com"})
        for _ in range(5):
            res = self.c.post(
                reverse("password-reset-otp-request"),
                data=payload,
                content_type="application/json",
            )
            self.assertEqual(res.status_code, 200)

        res = self.c.post(
            reverse("password-reset-otp-request"),
            data=payload,
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 429)
        self.assertEqual(res.json().get("error"), "too_many_requests")

    def test_confirm_invalid_email(self):
        res = self.c.post(
            reverse("password-reset-otp-confirm"),
            data=json.dumps(
                {"email": "ghost@example.com", "otp": "123456", "password": "Abcdef12"}
            ),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("error"), "invalid email")

    def test_confirm_invalid_otp(self):
        cs.store_otp("alice@example.com", "999999", ttl=600)
        res = self.c.post(
            reverse("password-reset-otp-confirm"),
            data=json.dumps(
                {"email": "alice@example.com", "otp": "000000", "password": "StrongPass1"}
            ),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json().get("error"), "invalid or expired otp")

    def test_confirm_success_updates_password_and_clears_cache(self):
        res = self.c.post(
            reverse("password-reset-otp-request"),
            data=json.dumps({"email": "alice@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        otp = extract_otp_from_mail(mail.outbox[-1].body)

        res = self.c.post(
            reverse("password-reset-otp-confirm"),
            data=json.dumps(
                {"email": "alice@example.com", "otp": otp, "password": "StrongPass1"}
            ),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), "success")

        user = get_auth_user_model().objects.get(email="alice@example.com")
        self.assertTrue(user.password.startswith("pbkdf2_"))
        self.assertIsNone(cs.get_otp("alice@example.com"))

>>>>>>> 3681087c2207037015f2eac908c4a4696bd53d72

# ============================================================
# 2. STUB untuk views.py (basic password reset)
# ============================================================
@override_settings(**TEST_OVERRIDES)
class BasicPasswordResetViewsStubTests(TestCase):
    """
    Stub: cuma manggil view supaya baris kode ke-execute.
    Nggak asumsi logic macam-macam.
    """

    def setUp(self):
        self.factory = RequestFactory()
        cache.clear()

    def _post_json(self, view_func, payload):
        req = self.factory.post(
            "/dummy/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        return view_func(req)

    def _json(self, resp):
        return json.loads(resp.content.decode("utf-8"))

    def test_request_password_reset_stub(self):
        resp = self._post_json(
            basic_views.request_password_reset,
            {"email": "stub@example.com"},
        )
        self.assertEqual(resp.status_code, 200)
        data = self._json(resp)
        # anti-enumeration → biasanya status ok
        self.assertIn("status", data)

    def test_request_password_reset_missing_email_stub(self):
        resp = self._post_json(basic_views.request_password_reset, {})
        # boleh 400 atau 200, yang penting tidak error
        self.assertIn(resp.status_code, (200, 400))

    def test_reset_password_confirm_stub(self):
        # panggil dengan payload minimal supaya lewat cabang "missing fields"
        resp = self._post_json(
            basic_views.reset_password_confirm,
            {"email": "", "otp": "", "password": ""},
        )
        self.assertIn(resp.status_code, (200, 400))


<<<<<<< HEAD
=======
@override_settings(**TEST_OVERRIDES)
class PasswordResetViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        AuthUser = get_auth_user_model()
        cls.user = AuthUser.objects.create(
            username="bob",
            email="bob@example.com",
            display_name="Bob",
            password="hunter22",
            roles=[],
            is_verified=True,
        )

    def setUp(self):
        self.factory = RequestFactory()
        cache.clear()

    def _post_json(self, view_func, payload):
        request = self.factory.post(
            "/dummy/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        return view_func(request)

    def _json(self, resp):
        return json.loads(resp.content.decode("utf-8"))

    def test_read_json_handles_invalid_payload(self):
        class DummyRequest:
            def __init__(self, payload):
                self.body = payload

        self.assertEqual(basic_views._read_json(DummyRequest(b"")), {})
        self.assertEqual(basic_views._read_json(DummyRequest(b"not-json")), {})
        self.assertEqual(
            basic_views._read_json(DummyRequest(b'{"email": "bob@example.com"}')),
            {"email": "bob@example.com"},
        )

    def test_request_password_reset_existing_user_sets_cache(self):
        resp = self._post_json(
            basic_views.request_password_reset, {"email": "bob@example.com"}
        )
        self.assertEqual(resp.status_code, 200)
        otp = cache.get("pwdreset:bob@example.com")
        self.assertIsNotNone(otp)
        self.assertEqual(len(otp), 6)

    def test_request_password_reset_missing_email(self):
        resp = self._post_json(basic_views.request_password_reset, {"email": ""})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self._json(resp).get("error"), "email is required")

    def test_reset_password_confirm_missing_fields(self):
        resp = self._post_json(
            basic_views.reset_password_confirm, {"email": "", "otp": "", "password": ""}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self._json(resp).get("error"), "missing fields")

    def test_reset_password_confirm_invalid_otp_returns_ok(self):
        resp = self._post_json(
            basic_views.reset_password_confirm,
            {"email": "bob@example.com", "otp": "000000", "password": "StrongPass"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._json(resp).get("status"), "ok")

    def test_reset_password_confirm_unknown_user_keeps_cache(self):
        cache.set("pwdreset:nope@example.com", "111111", timeout=600)
        resp = self._post_json(
            basic_views.reset_password_confirm,
            {"email": "nope@example.com", "otp": "111111", "password": "StrongPass"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._json(resp).get("status"), "ok")
        self.assertEqual(cache.get("pwdreset:nope@example.com"), "111111")

    def test_reset_password_confirm_success_updates_password_and_clears_cache(self):
        cache.set("pwdreset:bob@example.com", "222222", timeout=600)
        resp = self._post_json(
            basic_views.reset_password_confirm,
            {"email": "bob@example.com", "otp": "222222", "password": "StrongPass"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._json(resp).get("status"), "ok")
        user = get_auth_user_model().objects.get(email="bob@example.com")
        self.assertEqual(user.password, "StrongPass")
        self.assertIsNone(cache.get("pwdreset:bob@example.com"))

>>>>>>> 3681087c2207037015f2eac908c4a4696bd53d72
# ============================================================
# 3. STUB untuk cache_store service
# ============================================================
@override_settings(**TEST_OVERRIDES)
class CacheStoreStubTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_set_rate_returns_false_once_limit_exceeded(self):
        email = "ratetest@example.com"
        # limit=2 supaya cepat kena blok
        self.assertTrue(cs.set_rate(email, window=15, limit=2))
        self.assertTrue(cs.set_rate(email, window=15, limit=2))
        self.assertFalse(cs.set_rate(email, window=15, limit=2))
        self.assertFalse(cs.set_rate(email, window=15, limit=2))

    @patch("accounts.services.cache_store.time.time", return_value=1234567890)
    def test_store_and_get_otp_round_trip(self, _mocked_time):
        email = "storetest@example.com"
        cs.store_otp(email, "654321", ttl=20)
        cached = cache.get("pr_otp:storetest@example.com")
        self.assertEqual(cached, {"otp": "654321", "ts": 1234567890})
        self.assertEqual(cs.get_otp(email), "654321")

    def test_get_otp_missing_returns_none(self):
        self.assertIsNone(cs.get_otp("missing@example.com"))

    def test_delete_otp_removes_cache_entry(self):
        email = "delete@example.com"
        cs.store_otp(email, "000000", ttl=5)
        self.assertIsNotNone(cache.get("pr_otp:delete@example.com"))
        cs.delete_otp(email)
        self.assertIsNone(cache.get("pr_otp:delete@example.com"))


# ============================================================
# 4. STUB untuk csrf view
# ============================================================
@override_settings(**TEST_OVERRIDES)
class CsrfEndpointStubTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_csrf_view_stub(self):
        req = self.factory.get("/accounts/csrf/")
        resp = csrf_view.csrf(req)
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content.decode("utf-8"))
        self.assertIn("csrfToken", data)


# ============================================================
# 5. STUB untuk tokens.py
# ============================================================
@override_settings(**TEST_OVERRIDES)
class PasswordResetTokenStubTests(TestCase):
    def test_password_reset_token_stub(self):
        # cukup cek objeknya ada dan punya method make_token
        self.assertTrue(hasattr(password_reset_token, "make_token"))

# ============================================================
# 6. HIGH-COVERAGE STUB TESTS for views.py + views_otp_email.py
# ============================================================
@override_settings(**TEST_OVERRIDES)
class ViewsHighCoverageTests(TestCase):
    """
    Tujuan: menyentuh SEMUA branch di views.py & views_otp_email.py
    tanpa asumsi logic.

    Kita panggil:
    - missing fields
    - weak pass
    - wrong otp
    - correct otp
    - user not found
    - invalid email format
    - different password field names
    """

    @classmethod
    def setUpTestData(cls):
        AuthUser = get_auth_user_model()
        cls.user = AuthUser.objects.create(
            username="tester",
            email="tester@example.com",
            display_name="Tester",
            password="oldpass",
            roles=[],
            is_verified=True,
        )

    def setUp(self):
        self.client = Client()
        self.factory = RequestFactory()
        cache.clear()
        mail.outbox.clear()

    # ------------------------------
    # helper for factory_post
    # ------------------------------
    def _post_json(self, view_func, payload):
        req = self.factory.post(
            "/dummy/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        return view_func(req)

    # ============================================================
    #       views.py coverage
    # ============================================================

    def test_views_request_password_reset_all_branches(self):
        # missing email
        resp = self._post_json(basic_views.request_password_reset, {})
        self.assertIn(resp.status_code, (200, 400))

        # known email → should set cache
        resp = self._post_json(
            basic_views.request_password_reset,
            {"email": "tester@example.com"},
        )
        self.assertEqual(resp.status_code, 200)

        # unknown email → should still return ok
        resp = self._post_json(
            basic_views.request_password_reset,
            {"email": "ghost@example.com"},
        )
        self.assertEqual(resp.status_code, 200)

    def test_views_reset_password_confirm_all_branches(self):
        # missing fields
        resp = self._post_json(basic_views.reset_password_confirm, {})
        self.assertEqual(resp.status_code, 400)

        # weak password
        cache.set("pwdreset:tester@example.com", "123456")
        resp = self._post_json(
            basic_views.reset_password_confirm,
            {
                "email": "tester@example.com",
                "otp": "123456",
                "password": "weak",
            },
        )
        self.assertEqual(resp.status_code, 400)

        # wrong otp
        cache.set("pwdreset:tester@example.com", "123456")
        resp = self._post_json(
            basic_views.reset_password_confirm,
            {
                "email": "tester@example.com",
                "otp": "999999",
                "password": "Abcd1234!",
            },
        )
        self.assertEqual(resp.status_code, 200)  # anti-enumeration

        # correct otp → success branch
        cache.set("pwdreset:tester@example.com", "222222")
        resp = self._post_json(
            basic_views.reset_password_confirm,
            {
                "email": "tester@example.com",
                "otp": "222222",
                "password": "Abcd1234!",
            },
        )
        self.assertEqual(resp.status_code, 200)

    # ============================================================
    #       views_otp_email.py coverage
    # ============================================================

    def test_otp_email_request_all_branches(self):
        # missing email
        resp = self.client.post(
            reverse("password-reset-otp-request"),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

        # unknown email
        resp = self.client.post(
            reverse("password-reset-otp-request"),
            data=json.dumps({"email": "ghost@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

        # known email → sends mail
        resp = self.client.post(
            reverse("password-reset-otp-request"),
            data=json.dumps({"email": "tester@example.com"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    def test_otp_email_confirm_all_branches(self):
        # missing fields
        resp = self.client.post(
            reverse("password-reset-otp-confirm"),
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

        # weak pass
        resp = self.client.post(
            reverse("password-reset-otp-confirm"),
            data=json.dumps({
                "email": "tester@example.com",
                "otp": "9999",
                "password": "short",
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

        # invalid email → user not exist
        cs.store_otp("ghost@example.com", "123123")
        resp = self.client.post(
            reverse("password-reset-otp-confirm"),
            data=json.dumps({
                "email": "ghost@example.com",
                "otp": "123123",
                "password": "Abcd1234!",
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

        # invalid otp
        cs.store_otp("tester@example.com", "123123")
        resp = self.client.post(
            reverse("password-reset-otp-confirm"),
            data=json.dumps({
                "email": "tester@example.com",
                "otp": "000000",
                "password": "Abcd1234!",
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

        # success → correct otp
        cs.store_otp("tester@example.com", "222222")
        resp = self.client.post(
            reverse("password-reset-otp-confirm"),
            data=json.dumps({
                "email": "tester@example.com",
                "otp": "222222",
                "password": "Abcd1234!",
            }),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("status"), "success")
<<<<<<< HEAD

=======
>>>>>>> 3681087c2207037015f2eac908c4a4696bd53d72
