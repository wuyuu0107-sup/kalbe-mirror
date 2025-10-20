from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()

class BreadcrumbsAPITests(TestCase):
    """Failing test first: ensures /dashboard/breadcrumbs/ endpoint exists and returns expected JSON"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="hafizh", password="12345")
        self.client.login(username="hafizh", password="12345")

    def test_missing_path_returns_400(self):
        """If no ?path= param is given, should return 400 Bad Request"""
        url = reverse("dashboard:breadcrumbs")
        res = self.client.get(url)
        # we expect it to fail right now because endpoint doesn't exist yet
        self.assertEqual(res.status_code, 400)

    def test_basic_breadcrumbs_structure(self):
        """
        /dashboard/breadcrumbs/?path=/annotation/123/edit
        should return a JSON list of {'href','label'}
        """
        url = reverse("dashboard:breadcrumbs")
        res = self.client.get(url, {"path": "/annotation/123/edit"})
        self.assertEqual(res.status_code, 200)

        data = res.json()
        # Should be a list of dicts
        self.assertIsInstance(data, list)
        self.assertTrue(all("href" in c and "label" in c for c in data))
        # Last label should be 'Edit'
        self.assertEqual(data[-1]["label"], "Edit")
