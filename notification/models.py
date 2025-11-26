from django.db import models
from authentication.models import User

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('ocr.completed', 'Pemrosesan OCR Selesai'),
        ('ocr.failed', 'Pemrosesan OCR Gagal'),
        ('chat.reply', 'Respons Chat Baru'),
        ('system', 'Notifikasi Sistem'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=50, choices=NOTIFICATION_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    job_id = models.CharField(max_length=255, blank=True)
    data = models.JSONField(default=dict)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.user.username}"
