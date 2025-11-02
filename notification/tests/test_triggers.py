from unittest.mock import patch
from django.test import TestCase
from authentication.models import User
from notification import triggers
from notification.models import Notification
import uuid

class NotificationTriggersTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            user_id=uuid.uuid4(),
            username='testuser',
            display_name='Test User',
            email='test@example.com',
            password='testpass123',
            is_verified=True
        )

    @patch('notification.triggers.sse_send')
    def test_notify_without_user_id(self, mock_sse_send):
        """Test notify function without user_id - should not create persistent notification"""
        triggers.notify('session123', 'test.type', data={'key': 'value'}, job_id='job123')
        mock_sse_send.assert_called_once_with('session123', 'test.type', data={'key': 'value'}, job_id='job123', user_id=None)
        # Should not create notification in DB
        self.assertEqual(Notification.objects.count(), 0)

    @patch('notification.triggers.sse_send')
    def test_notify_with_user_id(self, mock_sse_send):
        """Test notify function with user_id - should create persistent notification"""
        triggers.notify('session123', 'test.type', data={'key': 'value'}, job_id='job123', user_id=str(self.user.user_id))
        mock_sse_send.assert_called_once_with('session123', 'test.type', data={'key': 'value'}, job_id='job123', user_id=str(self.user.user_id))
        # Should create notification in DB
        self.assertEqual(Notification.objects.count(), 1)
        notification = Notification.objects.first()
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.type, 'test.type')
        self.assertEqual(notification.job_id, 'job123')

    @patch('notification.triggers.sse_send')
    def test_notify_ocr_completed(self, mock_sse_send):
        """Test OCR completed notification trigger"""
        triggers.notify_ocr_completed('session123', path='test.csv', size=1024, job_id='job123', user_id=str(self.user.user_id))
        mock_sse_send.assert_called_once()
        # Check notification was created
        notification = Notification.objects.get(user=self.user)
        self.assertEqual(notification.type, 'ocr.completed')
        self.assertIn('test.csv', notification.message)

    @patch('notification.triggers.sse_send')
    def test_notify_ocr_failed(self, mock_sse_send):
        """Test OCR failed notification trigger"""
        triggers.notify_ocr_failed('session123', path='test.csv', reason='error', job_id='job123', user_id=str(self.user.user_id))
        mock_sse_send.assert_called_once()
        # Check notification was created
        notification = Notification.objects.get(user=self.user)
        self.assertEqual(notification.type, 'ocr.failed')
        self.assertIn('error', notification.message)

    @patch('notification.triggers.sse_send')
    def test_notify_chat_reply(self, mock_sse_send):
        """Test chat reply notification trigger"""
        triggers.notify_chat_reply('session123', job_id='job123', user_id=str(self.user.user_id))
        mock_sse_send.assert_called_once()
        # Check notification was created
        notification = Notification.objects.get(user=self.user)
        self.assertEqual(notification.type, 'chat.reply')
        self.assertIn('respons', notification.message)

    def test_get_notification_title(self):
        """Test notification title generation"""
        self.assertEqual(triggers.get_notification_title('ocr.completed', {}), 'Pemrosesan OCR Selesai')
        self.assertEqual(triggers.get_notification_title('ocr.failed', {}), 'Pemrosesan OCR Gagal')
        self.assertEqual(triggers.get_notification_title('chat.reply', {}), 'Respons Chat Baru')
        self.assertEqual(triggers.get_notification_title('unknown', {}), 'Notifikasi')

    def test_get_notification_message(self):
        """Test notification message generation"""
        # OCR completed
        msg = triggers.get_notification_message('ocr.completed', {'path': 'file.csv'})
        self.assertIn('file.csv', msg)
        self.assertIn('berhasil diproses', msg)

        # OCR failed
        msg = triggers.get_notification_message('ocr.failed', {'path': 'file.csv', 'reason': 'blurred'})
        self.assertIn('file.csv', msg)
        self.assertIn('blurred', msg)

        # Chat reply
        msg = triggers.get_notification_message('chat.reply', {})
        self.assertIn('respons baru', msg)

        # System
        msg = triggers.get_notification_message('system', {'message': 'test'})
        self.assertEqual(msg, 'test')

    @patch('notification.triggers.sse_send')
    def test_notify_with_invalid_user_id(self, mock_sse_send):
        """Test notify function with invalid user_id - should skip creating notification"""
        # Use a valid UUID format but non-existent user
        non_existent_uuid = '12345678-1234-5678-9012-123456789012'
        triggers.notify('session123', 'test.type', data={'key': 'value'}, job_id='job123', user_id=non_existent_uuid)
        mock_sse_send.assert_called_once_with('session123', 'test.type', data={'key': 'value'}, job_id='job123', user_id=non_existent_uuid)
        # Should not create notification in DB due to non-existent user
        self.assertEqual(Notification.objects.count(), 0)
