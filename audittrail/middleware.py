# audittrail/middleware.py
import json
from django.utils.deprecation import MiddlewareMixin
from django.db.models import Q
from django.db import DatabaseError, ProgrammingError

from audittrail.models import ActivityLog
from audittrail.services import log_activity

AUDIT_SESSION_KEY = "audit_username"


def _get_last_known_username():
    """
    Fallback: if we have no user and no session, grab the most recent
    login/OCR event that actually had a username.
    """
    last = (
        ActivityLog.objects
        .filter(
            Q(event_type=ActivityLog.EventType.USER_LOGIN)
            | Q(event_type=ActivityLog.EventType.OCR_UPLOADED),
            metadata__username__isnull=False,
        )
        .order_by("-created_at")
        .first()
    )
    if last:
        return last.metadata.get("username") or ""
    return ""


def _safe_get_last_known_username():
    """
    Same as _get_last_known_username but will NOT crash test runs
    (e.g. SimpleTestCase) that disallow DB access.
    """
    try:
        return _get_last_known_username()
    except (DatabaseError, ProgrammingError, Exception):
        # in tests or during startup, just skip DB fallback
        return ""


class AuditTrailMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Initialise event + capture raw body
        request._audittrail_event_type = None
        self._capture_raw_body(request)

        # Compute and expose effective username
        request.audit_username = self._get_effective_username(request)

        # Decide what event type (if any) this request represents
        request._audittrail_event_type = self._get_event_type(
            request.path,
            request.method.upper(),
        )

        return None

    def _capture_raw_body(self, request) -> None:
        try:
            request._audittrail_raw_body = request.body
        except Exception:
            request._audittrail_raw_body = b""

    def _get_effective_username(self, request) -> str:
        """
        Resolve the username to associate with this request using:
        1. authenticated user
        2. session-stored username
        3. DB fallback (_safe_get_last_known_username) or 'anonymous'
        """
        user = getattr(request, "user", None)
        username = ""

        # 1) authenticated user
        if user is not None and getattr(user, "is_authenticated", False):
            username = getattr(user, "username", "") or ""

        # 2) session-based username
        elif hasattr(request, "session"):
            username = request.session.get(AUDIT_SESSION_KEY, "") or ""

        # 3) DB fallback or 'anonymous'
        if not username:
            username = _safe_get_last_known_username() or "anonymous"

        return username

    def _get_event_type(self, path: str, method: str):
        """
        Map (path, method) to ActivityLog.EventType or None.
        Keeping the logic flat with early returns to minimise complexity.
        """
        if path == "/auth/login/":
            return ActivityLog.EventType.USER_LOGIN

        if path == "/ocr/" and method == "POST":
            return ActivityLog.EventType.OCR_UPLOADED

        if path in ("/dashboard/recent-features/", "//dashboard/recent-features/") and method == "GET":
            return ActivityLog.EventType.DASHBOARD_VIEWED

        if path == "/save-to-database/create/" and method == "POST":
            return ActivityLog.EventType.DATASET_SAVED

        if path.startswith("/api/v1/comments/") and method in ("POST", "PUT", "PATCH", "DELETE"):
            return ActivityLog.EventType.ANNOTATION_UPDATED

        if path.startswith("/api/v1/annotations/"):
            return ActivityLog.EventType.FEATURE_USED

        if path.startswith("/api/v1/documents/") and method in ("PATCH", "PUT"):
            return ActivityLog.EventType.ANNOTATION_UPDATED

        if path.startswith("/api/chat/"):
            return ActivityLog.EventType.FEATURE_USED

        if path == "/auth/api/protected-endpoint/" and method == "GET":
            return ActivityLog.EventType.FEATURE_USED

        return None

    # ---------------- refactored process_response ----------------

    def process_response(self, request, response):
        event_type = getattr(request, "_audittrail_event_type", None)
        if not self._should_log(event_type, response):
            return response

        base_meta = self._build_base_meta(request, response)
        user = getattr(request, "user", None)
        is_auth = bool(user and user.is_authenticated)
        precomputed_username = getattr(request, "audit_username", "") or ""

        # 1) Login flow
        if event_type == ActivityLog.EventType.USER_LOGIN:
            self._handle_login_event(
                request=request,
                response=response,
                base_meta=base_meta,
                user=user,
                is_auth=is_auth,
                event_type=event_type,
            )
            return response

        # 2) OCR upload flow
        if event_type == ActivityLog.EventType.OCR_UPLOADED:
            self._handle_ocr_event(
                request=request,
                response=response,
                base_meta=base_meta,
                user=user,
                is_auth=is_auth,
                event_type=event_type,
                precomputed_username=precomputed_username,
            )
            return response

        # 3) Normal authenticated feature usage
        if is_auth:
            self._handle_authenticated_event(
                request=request,
                response=response,
                base_meta=base_meta,
                user=user,
                event_type=event_type,
            )
            return response

        # 4) Anonymous feature usage
        self._handle_anonymous_event(
            request=request,
            response=response,
            base_meta=base_meta,
            event_type=event_type,
            precomputed_username=precomputed_username,
        )
        return response

    # ---------- helpers for process_response ----------

    def _should_log(self, event_type, response) -> bool:
        return bool(event_type and response.status_code < 400)

    def _build_base_meta(self, request, response) -> dict:
        return {
            "path": request.path,
            "method": request.method,
            "status_code": response.status_code,
            "querystring": request.META.get("QUERY_STRING", ""),
        }

    def _extract_login_username(self, request) -> str:
        raw = getattr(request, "_audittrail_raw_body", b"") or b""
        try:
            payload = json.loads(raw.decode() or "{}")
        except Exception:
            payload = {}

        guessed_username = (
            payload.get("username")
            or payload.get("email")
            or payload.get("user")
            or ""
        )

        if not guessed_username and hasattr(request, "POST"):
            guessed_username = (
                request.POST.get("username")
                or request.POST.get("email")
                or ""
            )

        return guessed_username or ""

    def _handle_login_event(self, request, response, base_meta, user, is_auth, event_type):
        guessed_username = self._extract_login_username(request)

        if guessed_username and hasattr(request, "session"):
            request.session[AUDIT_SESSION_KEY] = guessed_username

        log_activity(
            user=user if is_auth else None,
            event_type=event_type,
            request=request,
            metadata={**base_meta, "username": guessed_username},
        )

    def _resolve_ocr_username(self, user, is_auth, precomputed_username: str) -> str:
        if is_auth and user is not None:
            return user.username
        return precomputed_username or _safe_get_last_known_username() or "anonymous"

    def _handle_ocr_event(
        self,
        request,
        response,
        base_meta,
        user,
        is_auth,
        event_type,
        precomputed_username: str,
    ):
        ocr_username = self._resolve_ocr_username(user, is_auth, precomputed_username)

        if hasattr(request, "session"):
            request.session[AUDIT_SESSION_KEY] = ocr_username

        log_activity(
            user=user if is_auth else None,
            event_type=event_type,
            request=request,
            metadata={**base_meta, "username": ocr_username},
        )

    def _handle_authenticated_event(self, request, response, base_meta, user, event_type):
        if hasattr(request, "session"):
            request.session[AUDIT_SESSION_KEY] = user.username

        log_activity(
            user=user,
            event_type=event_type,
            request=request,
            metadata={**base_meta, "username": user.username},
        )

    def _handle_anonymous_event(self, request, response, base_meta, event_type, precomputed_username: str):
        session_username = ""
        if hasattr(request, "session"):
            session_username = request.session.get(AUDIT_SESSION_KEY, "") or ""

        final_username = (
            session_username
            or precomputed_username
            or _safe_get_last_known_username()
            or "anonymous"
        )

        log_activity(
            user=None,
            event_type=event_type,
            request=request,
            metadata={**base_meta, "username": final_username},
        )
