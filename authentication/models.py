from django.db import models
import uuid
from django.core.validators import MinLengthValidator


class User(models.Model):
    user_id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    username = models.CharField(
        max_length=150,
        unique=True
    )
    password = models.CharField(
        max_length=255,
        validators=[MinLengthValidator(8)]
    )
    display_name = models.CharField(
        max_length=150
    )
    email = models.EmailField(
        unique=True
    )
    last_accessed = models.DateTimeField(
        auto_now=True
    )
    roles = models.JSONField(  
        default=list
    )

    is_verified = models.BooleanField(default=False)
    verification_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    USERNAME_FIELD = 'username'  
    REQUIRED_FIELDS = ['email']  

    def __str__(self):
        return self.username