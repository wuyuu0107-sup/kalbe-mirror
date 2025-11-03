# audittrail/models.py
from django.db import models
from django.conf import settings


class ActivityLog(models.Model):
    class EventType(models.TextChoices):
        # auth / session
        USER_LOGIN = "USER_LOGIN", "User login"
        USER_LOGOUT = "USER_LOGOUT", "User logout"

        # dashboard / feature
        DASHBOARD_VIEWED = "DASHBOARD_VIEWED", "Dashboard viewed"
        FEATURE_USED = "FEATURE_USED", "Feature used"

        # ocr
        OCR_UPLOADED = "OCR_UPLOADED", "OCR file uploaded"
        OCR_PROCESSED = "OCR_PROCESSED", "OCR processed"

        # annotation
        ANNOTATION_CREATED = "ANNOTATION_CREATED", "Annotation created"
        ANNOTATION_UPDATED = "ANNOTATION_UPDATED", "Annotation updated"

        # dataset / csv
        DATASET_SAVED = "DATASET_SAVED", "Dataset saved"
        DATASET_VIEWED = "DATASET_VIEWED", "Dataset viewed"
        DATASET_DOWNLOADED = "DATASET_DOWNLOADED", "Dataset downloaded"

    # who did it (FK)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activity_logs",
    )

    # snapshot of username at the time of the event
    username = models.CharField(max_length=150, blank=True, default="")

    # what happened
    event_type = models.CharField(max_length=64, choices=EventType.choices)

    # when
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # target info (denormalized)
    target_app = models.CharField(max_length=64, blank=True, default="")
    target_model = models.CharField(max_length=64, blank=True, default="")
    target_id = models.CharField(max_length=64, blank=True, default="")
    target_repr = models.CharField(max_length=255, blank=True, default="")

    # request context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    request_id = models.CharField(max_length=128, blank=True, default="")

    # extra
    metadata = models.JSONField(blank=True, default=dict)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["event_type", "created_at"]),
            models.Index(fields=["target_app", "target_model", "target_id"]),
        ]

    def __str__(self):
        who = self.username or (self.user.username if self.user_id else "system")
        return f"[{self.event_type}] by {who} at {self.created_at}"
