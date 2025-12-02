from django.utils import timezone
from django.db.models import Max, Count
from authentication.models import User
from dashboard.models import FeatureUsage

def record_feature_use(request, feature_key: str):
    try:
        real_user = None
        print("user_id:", request.session.get("user_id"))

        if not real_user and request:
            user_id = request.session.get("user_id")
            if user_id:
                real_user = User.objects.filter(user_id=user_id).first()

        FeatureUsage.objects.create(
            user=real_user,
            feature_key=feature_key,
            used_at=timezone.now(),
        )

    except Exception as e:
        print(f"[record_feature_use] Error: {e}")


def get_recent_features(user, limit=4):
    try:
        if not user:
            return []
        
        features = (
            FeatureUsage.objects.filter(user=user)
            .values("feature_key")
            .annotate(last_used_at=Max("used_at"), count=Count("id"))
            .order_by("-last_used_at", "feature_key")[:limit]
        )
        return list(features)
    
    except Exception as e:
        print(f"[get_recent_features] Error: {e}")
        return []