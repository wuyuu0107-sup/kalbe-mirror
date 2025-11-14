from django.test import TestCase
from authentication.models import User
from notification.models import Notification
import uuid

class NotificationModelTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            user_id=uuid.uuid4(),
            username='testuser',
            display_name='Test User',
            email='test@example.com',
            password='testpass123',
            is_verified=True
        )

    def test_notification_str_method(self):
        """Test the __str__ method of Notification model."""
        notification = Notification.objects.create(
            user=self.user,
            title='Test Notification',
            message='This is a test notification',
            type='system'
        )
        expected_str = f"{notification.title} - {self.user.username}"
        self.assertEqual(str(notification), expected_str)
