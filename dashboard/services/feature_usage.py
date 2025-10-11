from django.db.models import Max, Count
from django.utils import timezone
from dashboard.models import FeatureUsage

def record_feature_use(user, feature_key: str):
    try:
        is_valid = bool(user and getattr(user, "is_authenticated", False))
    except Exception:
        is_valid = False

    FeatureUsage.objects.create(
        user=user if is_valid else None,
        feature_key=feature_key,
        used_at = timezone.now(),
    )

def get_recent_features(user, limit=4):
    features = FeatureUsage.objects.filter(user=user)
    agg =  (
        features.values("feature_key")
            .annotate(last_used_at=Max("used_at"), count=Count("id"))     
            .order_by("-last_used_at", "feature_key")[:limit]
    )
    return list(agg)