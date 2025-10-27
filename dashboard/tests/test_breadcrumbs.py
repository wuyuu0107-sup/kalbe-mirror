from django.test import TestCase, Client
from authentication.models import User
from django.urls import reverse
from django.contrib.auth.hashers import make_password

class BreadcrumbsAPITests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create(
            username="alice",
            password=make_password("sTrongpassword!1",),
            display_name="Alice",
            email="alice@example.com",
            roles=["researcher"],
            is_verified=True
        )
        session = self.client.session
        session["user_id"] = str(self.user.user_id)
        session.save()

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
