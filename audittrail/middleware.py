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
        request._audittrail_event_type = None
        try:
            request._audittrail_raw_body = request.body
        except Exception:
            request._audittrail_raw_body = b""

        # 1. try authenticated user
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            effective_username = user.username
        else:
            # 2. try session
            if hasattr(request, "session"):
                effective_username = request.session.get(AUDIT_SESSION_KEY, "") or ""
            else:
                effective_username = ""

        # 3. final fallback: last known username from DB (safe)
        if not effective_username:
            effective_username = _safe_get_last_known_username() or "anonymous"

        # expose to views
        request.audit_username = effective_username

        path = request.path
        method = request.method.upper()

        if path == "/auth/login/":
            request._audittrail_event_type = ActivityLog.EventType.USER_LOGIN

        elif path == "/ocr/" and method == "POST":
            request._audittrail_event_type = ActivityLog.EventType.OCR_UPLOADED

        elif path in ("/dashboard/recent-features/", "//dashboard/recent-features/") and method == "GET":
            request._audittrail_event_type = ActivityLog.EventType.DASHBOARD_VIEWED

        elif path == "/save-to-database/create/" and method == "POST":
            request._audittrail_event_type = ActivityLog.EventType.DATASET_SAVED

        elif path.startswith("/api/v1/comments/") and method in ("POST", "PUT", "PATCH", "DELETE"):
            request._audittrail_event_type = ActivityLog.EventType.ANNOTATION_UPDATED

        elif path.startswith("/api/v1/annotations/"):
            request._audittrail_event_type = ActivityLog.EventType.FEATURE_USED

        elif path.startswith("/api/v1/documents/") and method in ("PATCH", "PUT"):
            request._audittrail_event_type = ActivityLog.EventType.ANNOTATION_UPDATED

        elif path.startswith("/api/chat/"):
            request._audittrail_event_type = ActivityLog.EventType.FEATURE_USED

        elif path == "/auth/api/protected-endpoint/" and method == "GET":
            request._audittrail_event_type = ActivityLog.EventType.FEATURE_USED

        return None

    def process_response(self, request, response):
        event_type = getattr(request, "_audittrail_event_type", None)
        if not event_type or response.status_code >= 400:
            return response

        base_meta = {
            "path": request.path,
            "method": request.method,
            "status_code": response.status_code,
            "querystring": request.META.get("QUERY_STRING", ""),
        }

        user = getattr(request, "user", None)
        is_auth = bool(user and user.is_authenticated)

        # whatever we computed earlier
        precomputed_username = getattr(request, "audit_username", "") or ""

        # --- 1) LOGIN: extract from payload, save, log ---
        if event_type == ActivityLog.EventType.USER_LOGIN:
            guessed_username = ""

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

            if guessed_username and hasattr(request, "session"):
                request.session[AUDIT_SESSION_KEY] = guessed_username

            log_activity(
                user=user if is_auth else None,
                event_type=event_type,
                request=request,
                metadata={**base_meta, "username": guessed_username},
            )
            return response

        # --- 2) OCR: mark and also store username for later requests ---
        if event_type == ActivityLog.EventType.OCR_UPLOADED:
            if is_auth:
                ocr_username = user.username
            else:
                ocr_username = precomputed_username or _safe_get_last_known_username() or "anonymous"

            if hasattr(request, "session"):
                request.session[AUDIT_SESSION_KEY] = ocr_username

            log_activity(
                user=user if is_auth else None,
                event_type=event_type,
                request=request,
                metadata={**base_meta, "username": ocr_username},
            )
            return response

        # --- 3) normal authenticated requests ---
        if is_auth:
            if hasattr(request, "session"):
                request.session[AUDIT_SESSION_KEY] = user.username

            log_activity(
                user=user,
                event_type=event_type,
                request=request,
                metadata={**base_meta, "username": user.username},
            )
            return response

        # --- 4) anonymous: reuse whatever we have, or DB fallback (safe) ---
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
        return response
