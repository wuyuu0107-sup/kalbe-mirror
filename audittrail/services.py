# audittrail/services.py
from django.contrib.auth import get_user_model

from .models import ActivityLog


def log_activity(*, user=None, event_type="", target=None, request=None, metadata=None):
    metadata = metadata or {}

    user_model = get_user_model()

    # figure out username first
    username = ""
    if user is not None and hasattr(user, "username"):
        username = user.username

    if not username and metadata.get("username"):
        username = metadata["username"]

    # make sure user is the right model; if not, fall back to username-only
    if user is not None and not isinstance(user, user_model):
        # keep the name, drop the FK
        if username and "username" not in metadata:
            metadata["username"] = username
        user = None

    target_app = target_model = target_id = target_repr = ""
    if target is not None:
        target_app = target._meta.app_label
        target_model = target._meta.model_name
        target_id = str(getattr(target, "pk", ""))
        target_repr = str(target)

    ip = request.META.get("REMOTE_ADDR") if request else None
    ua = request.META.get("HTTP_USER_AGENT", "") if request else ""
    req_id = request.META.get("X-Request-ID", "") if request else ""

    return ActivityLog.objects.create(
        user=user,
        username=username,
        event_type=event_type,
        target_app=target_app,
        target_model=target_model,
        target_id=target_id,
        target_repr=target_repr,
        ip_address=ip,
        user_agent=ua,
        request_id=req_id,
        metadata=metadata,
    )
