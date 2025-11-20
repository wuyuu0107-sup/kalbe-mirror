from django.db import models
import uuid

class PredictionResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sin = models.CharField(max_length=50, db_index=True, blank=True, null=True)
    subject_initials = models.CharField(max_length=20, blank=True, null=True)
    prediction = models.CharField(max_length=100)

    # optional link to your existing Patient model
    patient = models.ForeignKey(
        "patient.Patient",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="predictions",
    )

    # original input / full output / extras
    input_data = models.TextField(blank=True, null=True)
    meta = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Prediction Result"
        verbose_name_plural = "Prediction Results"

    def __str__(self):
        return f"{self.sin or 'N/A'} | {self.subject_initials or 'N/A'} → {self.prediction}"
