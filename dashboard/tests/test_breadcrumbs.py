from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()

class BreadcrumbsAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="u1", password="p")
        self.client.login(username="u1", password="p")

    def test_requires_path(self):
        url = reverse("dashboard:breadcrumbs")
        res = self.client.get(url)
        self.assertEqual(res.status_code, 400)

    def test_dashboard(self):
        url = reverse("dashboard:breadcrumbs")
        res = self.client.get(url, {"path": "/dashboard"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual([c["label"] for c in data], ["Home", "Dashboard"])

    def test_deep_path(self):
        url = reverse("dashboard:breadcrumbs")
        res = self.client.get(url, {"path": "/annotation/123/edit"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual([c["label"] for c in res.json()],
                         ["Home", "Annotations", "123", "Edit"])
