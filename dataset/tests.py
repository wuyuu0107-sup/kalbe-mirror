import os
import shutil
import tempfile

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse

from authentication.models import User
from .models import CSVFile


class DatasetFileManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Isolate media writes into a temp directory
        self._temp_media = tempfile.mkdtemp(prefix="test_media_")
        self._old_media_root = settings.MEDIA_ROOT
        settings.MEDIA_ROOT = self._temp_media

        # URLs
        self.list_create_url = reverse("csvfile_list_create")

        # Users
        self.researcher = User.objects.create(
            username="researcher_user",
            password="ResearcherPass123",
            display_name="Researcher User",
            email="researcher@example.com",
            roles=["researcher"],
            is_verified=True,
        )
        self.normal_user = User.objects.create(
            username="normal_user",
            password="UserPass123",
            display_name="Normal User",
            email="user@example.com",
            roles=["user"],
            is_verified=True,
        )
        self.unverified_researcher = User.objects.create(
            username="unverified_researcher",
            password="ResearcherPass123",
            display_name="Unverified Researcher",
            email="uresearcher@example.com",
            roles=["researcher"],
            is_verified=False,
        )

    def tearDown(self):
        # Restore settings and remove temp dir
        settings.MEDIA_ROOT = self._old_media_root
        shutil.rmtree(self._temp_media, ignore_errors=True)

    # Helpers
    def _login(self, user: User):
        session = self.client.session
        session["user_id"] = str(user.user_id)
        session["username"] = user.username
        session.save()

    def _upload_csv(self, name="sample.csv", content=b"a,b\n1,2\n"):
        file = SimpleUploadedFile(name, content, content_type="text/csv")
        resp = self.client.post(self.list_create_url, {"file": file})
        return resp

    # Access control tests
    def test_unauthenticated_access_is_forbidden(self):
        # List
        r = self.client.get(self.list_create_url)
        self.assertEqual(r.status_code, 403)
        # Create
        file = SimpleUploadedFile("x.csv", b"x,y\n", content_type="text/csv")
        r = self.client.post(self.list_create_url, {"file": file})
        self.assertEqual(r.status_code, 403)

    def test_non_admin_authenticated_access_is_forbidden(self):
        self._login(self.normal_user)
        # List
        r = self.client.get(self.list_create_url)
        self.assertEqual(r.status_code, 403)
        # Create
        file = SimpleUploadedFile("x.csv", b"x,y\n", content_type="text/csv")
        r = self.client.post(self.list_create_url, {"file": file})
        self.assertEqual(r.status_code, 403)

    def test_unverified_researcher_is_forbidden(self):
        self._login(self.unverified_researcher)
        r = self.client.get(self.list_create_url)
        self.assertEqual(r.status_code, 403)

    # CRUD + download tests
    def test_researcher_can_upload_list_retrieve_download_and_delete(self):
        self._login(self.researcher)

        # Upload
        upload_resp = self._upload_csv()
        self.assertEqual(upload_resp.status_code, 201, upload_resp.content)
        data = upload_resp.json()
        self.assertIn("id", data)
        self.assertIn("file_url", data)
        self.assertIn("filename", data)
        self.assertEqual(data["filename"], "sample.csv")
        self.assertTrue(str(data["file_url"]).startswith("http://testserver"))

        obj_id = data["id"]
        obj = CSVFile.objects.get(pk=obj_id)
        self.assertTrue(os.path.exists(obj.file_path.path))
        self.assertTrue(obj.file_path.name.startswith("csv_files/"))

        # List
        list_resp = self.client.get(self.list_create_url)
        self.assertEqual(list_resp.status_code, 200)
        payload = list_resp.json()
        items = payload["results"] if isinstance(payload, dict) and "results" in payload else payload
        self.assertTrue(any(it["id"] == obj_id for it in items))

        # Retrieve
        detail_url = reverse("csvfile_detail_destroy", kwargs={"pk": obj_id})
        detail_resp = self.client.get(detail_url)
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()["id"], obj_id)

        # Download
        download_url = reverse("csvfile_download", kwargs={"pk": obj_id})
        download_resp = self.client.get(download_url)
        self.assertEqual(download_resp.status_code, 200)
        disp = download_resp.headers.get("Content-Disposition", "")
        self.assertIn("attachment", disp)
        self.assertIn("sample.csv", disp)
        content = b"".join(download_resp.streaming_content)
        self.assertIn(b"a,b\n1,2\n", content)

        # Delete
        delete_resp = self.client.delete(detail_url)
        self.assertIn(delete_resp.status_code, (200, 204))
        # File should be removed from the filesystem
        self.assertFalse(os.path.exists(obj.file_path.path))
        self.assertFalse(CSVFile.objects.filter(pk=obj_id).exists())

    def test_upload_without_file_returns_400(self):
        self._login(self.researcher)
        resp = self.client.post(self.list_create_url, {})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("detail", resp.json())

    def test_download_missing_file_returns_404(self):
        self._login(self.researcher)
        # Upload one file
        upload_resp = self._upload_csv(name="missing.csv", content=b"col\nval\n")
        self.assertEqual(upload_resp.status_code, 201)
        obj_id = upload_resp.json()["id"]
        obj = CSVFile.objects.get(pk=obj_id)
        # Remove underlying file to simulate external deletion
        os.remove(obj.file_path.path)
        self.assertFalse(os.path.exists(obj.file_path.path))
        # Try download
        download_url = reverse("csvfile_download", kwargs={"pk": obj_id})
        download_resp = self.client.get(download_url)
        self.assertEqual(download_resp.status_code, 404)
