# audittrail/services.py
from .models import ActivityLog


def log_activity(*, user=None, event_type="", target=None, request=None, metadata=None):
    metadata = metadata or {}

    username = ""
    if user is not None and hasattr(user, "username"):
        username = user.username

    if not username and "username" in metadata and metadata["username"]:
        username = metadata["username"]

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
