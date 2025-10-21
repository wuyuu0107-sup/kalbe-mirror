from django.test import TestCase
from django.contrib.contenttypes.models import ContentType
from authentication.models import User
from .models import Activity
from .views import log_activity, ActivityViewSet

class ActivityModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username='testuser',
            password='testpass',
            email='testuser@example.com',
            is_verified=True,
            is_active=True,
            otp_code='123456'
        )

    def test_create_activity(self):
        activity = Activity.objects.create(
            user=self.user,
            activity_type='ocr',
            description='Test OCR activity',
        )
        self.assertEqual(activity.user, self.user)
        self.assertEqual(activity.activity_type, 'ocr')
        self.assertEqual(activity.description, 'Test OCR activity')
        self.assertIsNotNone(activity.created_at)

    def test_activity_str(self):
        activity = Activity.objects.create(
            user=self.user,
            activity_type='annotation',
            description='Test annotation',
        )
        self.assertIn(self.user.username, str(activity))
        self.assertIn('annotation', str(activity))

    def test_content_object(self):
        ct = ContentType.objects.get_for_model(User)
        activity = Activity.objects.create(
            user=self.user,
            activity_type='comment',
            description='Test comment',
            content_type=ct,
            object_id=self.user.user_id
        )
        self.assertEqual(activity.content_object, self.user)

class LogActivityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username='loguser',
            password='testpass',
            email='loguser@example.com',
            is_verified=True,
            is_active=True,
            otp_code='123456'
        )

    def test_log_activity_basic(self):
        activity = log_activity(
            user=self.user,
            activity_type='file_move',
            description='Moved a file'
        )
        self.assertEqual(activity.user, self.user)
        self.assertEqual(activity.activity_type, 'file_move')
        self.assertEqual(activity.description, 'Moved a file')

    def test_log_activity_with_content_object(self):
        activity = log_activity(
            user=self.user,
            activity_type='file_upload',
            description='Uploaded a file',
            content_object=self.user
        )
        self.assertEqual(activity.content_object, self.user)

class ActivityViewSetTest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username='apiuser',
            password='testpass',
            email='apiuser@example.com',
            is_verified=True,
            is_active=True,
            otp_code='123456'
        )
        Activity.objects.create(user=self.user, activity_type='ocr', description='API OCR')
        Activity.objects.create(user=self.user, activity_type='comment', description='API Comment')

    def test_list_activities_authenticated(self):
        self.client.force_login(self.user)
        # Set session data that the middleware expects
        session = self.client.session
        session['user_id'] = str(self.user.user_id)
        session['username'] = self.user.username
        session.save()
        response = self.client.get('/api/activities/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.json()) >= 2)

    def test_list_activities_unauthenticated(self):
        response = self.client.get('/api/activities/')
        self.assertEqual(response.status_code, 403)


class MiddlewareTest(TestCase):
    def test_user_in_request_middleware_anonymous(self):
        from .middleware import UserInRequestMiddleware
        from django.http import HttpResponse

        class Dummy:
            pass

        req = Dummy()
        # no user attribute -> middleware should simply return and not set attribute
        mw = UserInRequestMiddleware(get_response=lambda r: HttpResponse())
        mw.process_request(req)  # should not raise
        self.assertFalse(hasattr(req, 'user_for_logging'))

    def test_user_in_request_middleware_with_user(self):
        from .middleware import UserInRequestMiddleware
        from django.contrib.auth.models import AnonymousUser
        from django.http import HttpResponse

        class Dummy:
            pass

        req = Dummy()
        req.user = AnonymousUser()
        mw = UserInRequestMiddleware(get_response=lambda r: HttpResponse())
        mw.process_request(req)
        self.assertTrue(hasattr(req, 'user_for_logging'))
        self.assertEqual(req.user_for_logging, 'Anonymous')
