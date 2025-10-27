from unittest import TestCase, mock
from django.urls import reverse
from django.test import Client
import datetime as dt

class RecentFilesViewsTests(TestCase):
    def setUp(self):
        self.client = Client()

    @mock.patch("dashboard.views.get_recent_files")
    def test_recent_files_json_returns_iso(self, mock_service):
        mock_service.return_value = [
            {"name":"x.csv",
             "updated_at": dt.datetime(2025,10,7,12,0), 
             "size": 2048, 
             "path":"x.csv"}
        ]

        url = reverse("dashboard:recent-files-json", args=[10])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data[0]["name"], "x.csv")
        self.assertIn("T", data[0]["updated_at"])
        mock_service.assert_called_once_with(10)