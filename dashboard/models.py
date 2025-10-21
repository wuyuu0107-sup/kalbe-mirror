from django.db import models
from authentication.models import User

# Create your models here.
class FeatureUsage(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE, # delete usage logs if the user is deleted
        null = True,  # allow null (for anonymous access if needed)
        blank = True, # allow blank in admin/forms

        # optional: lets you do user.feature_usages.all()
        # related_name="feature_usages"
    )
    feature_key = models.CharField(max_length=128)
    used_at = models.DateTimeField(auto_now_add = True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "-used_at"]),
        ]
        ordering = ["-used_at"]

    def __str__(self):
        return f"{self.user} used {self.feature_key} at {self.used_at}"