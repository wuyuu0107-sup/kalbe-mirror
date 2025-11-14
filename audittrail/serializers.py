# audittrail/serializers.py
from rest_framework import serializers
from audittrail.models import ActivityLog


class ActivityLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActivityLog
        fields = [
            "id",
            "created_at",      # assuming your model has this
            "event_type",
            "username",
            "target_app",
            "target_model",
            "target_id",
            "target_repr",
            "ip_address",
            "user_agent",
            "request_id",
            "metadata",
        ]
