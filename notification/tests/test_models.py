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

    def test_create_notification_minimal_fields(self):
        notification = Notification.objects.create(
            user=self.user,
            title='Simple',
            message='Minimal message',
            type='system'
        )

        self.assertIsNotNone(notification.id)
        self.assertEqual(notification.is_read, False)
        self.assertIsNone(notification.job_id)
        self.assertEqual(notification.data, {})

    def test_jsonfield_accepts_complex_data(self):
        payload = {
            "ocr_id": "123",
            "pages": [1, 2, 3],
            "meta": {"confidence": 0.93}
        }

        notification = Notification.objects.create(
            user=self.user,
            title='OCR Complete',
            message='OCR finished',
            type='ocr.completed',
            data=payload
        )

        self.assertEqual(notification.data["ocr_id"], "123")
        self.assertEqual(notification.data["pages"], [1, 2, 3])
        self.assertAlmostEqual(notification.data["meta"]["confidence"], 0.93)

    def test_job_id_behavior(self):
        n1 = Notification.objects.create(
            user=self.user,
            title='With None',
            message='Test',
            type='system',
            job_id=None,
        )
        n2 = Notification.objects.create(
            user=self.user,
            title='With Empty',
            message='Test',
            type='system',
            job_id="",
        )

        self.assertIsNone(n1.job_id)
        self.assertEqual(n2.job_id, "")
    
    def test_notifications_are_ordered_by_created_at_desc(self):
        n1 = Notification.objects.create(
            user=self.user,
            title='Old',
            message='First',
            type='system'
        )

        n2 = Notification.objects.create(
            user=self.user,
            title='New',
            message='Second',
            type='system'
        )

        notifications = list(Notification.objects.all())
        self.assertEqual(notifications[0], n2)
        self.assertEqual(notifications[1], n1)

    def test_multiple_notifications_for_same_user(self):
        Notification.objects.create(
            user=self.user,
            title='One',
            message='Msg1',
            type='system'
        )
        Notification.objects.create(
            user=self.user,
            title='Two',
            message='Msg2',
            type='system'
        )

        count = Notification.objects.filter(user=self.user).count()
        self.assertEqual(count, 2)


