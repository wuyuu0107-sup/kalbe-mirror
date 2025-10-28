from functools import wraps
from dashboard.services.feature_usage import record_feature_use

# automatically records that the user accessed that feature
def track_feature(feature_key: str):
    def _decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            try:
                record_feature_use(request, feature_key)
            except Exception:
                # Safety: never break the user request because of telemetry
                pass
            return view_func(request, *args, **kwargs)
        return _wrapped
    return _decorator