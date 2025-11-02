from django.test import TestCase
from django.urls import reverse
from authentication.models import User
from ..models import Notification
import json

class NotificationViewsTestCase(TestCase):
    def setUp(self):
        import uuid
        self.user = User.objects.create(
            user_id=uuid.uuid4(),
            username='testuser',
            display_name='Test User',
            email='test@example.com',
            password='testpass123',
            is_verified=True
        )

        # Create some test notifications
        self.notification1 = Notification.objects.create(
            user=self.user,
            title='Test Notification 1',
            message='This is test notification 1',
            type='system'
        )
        self.notification2 = Notification.objects.create(
            user=self.user,
            title='Test Notification 2',
            message='This is test notification 2',
            type='ocr.completed',
            is_read=True
        )

    def test_notification_list(self):
        # Simulate session-based authentication
        session = self.client.session
        session['user_id'] = str(self.user.user_id)
        session.save()

        url = reverse('notification-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('notifications', data)
        self.assertIn('pagination', data)
        self.assertEqual(len(data['notifications']), 2)

    def test_mark_notification_read(self):
        # Simulate session-based authentication
        session = self.client.session
        session['user_id'] = str(self.user.user_id)
        session.save()

        url = reverse('mark-notification-read', kwargs={'notification_id': self.notification1.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.notification1.refresh_from_db()
        self.assertTrue(self.notification1.is_read)

    def test_mark_all_notifications_read(self):
        # Simulate session-based authentication
        session = self.client.session
        session['user_id'] = str(self.user.user_id)
        session.save()

        url = reverse('mark-all-read')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.notification1.refresh_from_db()
        self.assertTrue(self.notification1.is_read)

    def test_notification_count(self):
        # Simulate session-based authentication
        session = self.client.session
        session['user_id'] = str(self.user.user_id)
        session.save()

        url = reverse('notification-count')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('unread_count', data)
        self.assertEqual(data['unread_count'], 1)  # Only notification1 is unread

    def test_unauthenticated_access(self):
        url = reverse('notification-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 401)  # Unauthorized
