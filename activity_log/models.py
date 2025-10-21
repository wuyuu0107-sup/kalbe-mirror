from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.conf import settings

class Activity(models.Model):
    ACTIVITY_TYPES = (
        ('ocr', 'OCR Processing'),
        ('annotation', 'Document Annotation'),
        ('file_move', 'File Movement'),
        ('comment', 'Comment Added'),
        ('file_upload', 'File Upload'),
        ('folder_move', 'Folder Move'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,  # Keep activity records even if user is deleted
        null=True,
        related_name='activities'
    )
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Generic foreign key to allow linking to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
    object_id = models.CharField(max_length=50, null=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Activities'

    def __str__(self):
        return f"{self.user} - {self.activity_type} - {self.created_at}"
