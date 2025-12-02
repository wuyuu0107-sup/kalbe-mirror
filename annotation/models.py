# annotation/models.py
from django.db import models


class Document(models.Model):
    SOURCE_CHOICES = (
        ("json", "JSON"),
        ("pdf", "PDF"),
    )

    source = models.CharField(
        max_length=10,
        choices=SOURCE_CHOICES,
        default="json",
    )
    content_url = models.TextField(blank=True, default="")
    payload_json = models.JSONField(blank=True, null=True)
    meta = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    payload_json_text = models.TextField(blank=True, null=True)

    def __str__(self) -> str:
        return f"Document {self.pk} ({self.source})"


class Annotation(models.Model):
    """
    A generic drawing/region annotation for a given (document, patient).
    `drawing_data` is *frontend-defined* (e.g., [{tool:'pen', points:[[x,y],...]}]).
    """

    document = models.ForeignKey(
        Document,
        related_name="annotations",
        on_delete=models.CASCADE,
    )
    # NOTE: This now points to the *shared* Patient model in another app.
    # If your app label is not "patients", update the string below accordingly.
    patient = models.ForeignKey(
        "patient.Patient",
        related_name="annotations",
        on_delete=models.CASCADE,
    )
    label = models.CharField(max_length=128, blank=True, default="")
    # must be a JSON object or list (validated in serializer)
    drawing_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["document", "patient"]),
        ]

    def __str__(self) -> str:
        return f"Annotation {self.pk} on doc {self.document_id}"


class Comment(models.Model):
    document = models.ForeignKey(
        Document,
        related_name="comments",
        on_delete=models.CASCADE,
    )
    # Also reference the shared Patient model here; can be nullable.
    patient = models.ForeignKey(
        "patient.Patient",
        related_name="comments",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    author = models.CharField(max_length=128, blank=True, default="")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Comment {self.pk} on doc {self.document_id}"
