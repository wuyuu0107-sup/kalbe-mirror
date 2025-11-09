import os
import shutil
import tempfile

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.storage import default_storage
import unittest.mock as mock
from types import SimpleNamespace

from authentication.models import User
from save_to_database.models import CSV


class DatasetFileManagementTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Isolate media writes into a temp directory
        self._temp_media = tempfile.mkdtemp(prefix="test_media_")
        self._old_media_root = settings.MEDIA_ROOT
        settings.MEDIA_ROOT = self._temp_media
        # Reset default storage to use new MEDIA_ROOT
        _ = default_storage.location  # trigger setup
        default_storage._wrapped.location = settings.MEDIA_ROOT

        # URLs
        self.list_create_url = reverse("csvfile_list_create")
        self.folder_move_url = reverse("folder_move")

        # Users
        self.researcher = User.objects.create(
            username="researcher_user",
            password="ResearcherPass123",
            display_name="Researcher User",
            email="researcher@example.com",
            is_verified=True,
        )
        self.unverified_researcher = User.objects.create(
            username="unverified_researcher",
            password="ResearcherPass123",
            display_name="Unverified Researcher",
            email="uresearcher@example.com",
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
        self.assertTrue(data["filename"].startswith("sample"))
        self.assertTrue(str(data["file_url"]).startswith("http://testserver"))

        obj_id = data["id"]
        obj = CSV.objects.get(pk=obj_id)
        self.assertTrue(os.path.exists(obj.file.path))
        self.assertTrue(obj.file.name.startswith("datasets/csvs/"))

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
        self.assertIn("sample", disp)
        content = b"".join(download_resp.streaming_content)
        self.assertIn(b"a,b\n1,2\n", content)

        # Delete
        delete_resp = self.client.delete(detail_url)
        self.assertIn(delete_resp.status_code, (200, 204))
        # File should be removed from the filesystem
        self.assertFalse(os.path.exists(obj.file.path))
        self.assertFalse(CSV.objects.filter(pk=obj_id).exists())

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
        obj = CSV.objects.get(pk=obj_id)
        # Remove underlying file to simulate external deletion
        os.remove(obj.file.path)
        self.assertFalse(os.path.exists(obj.file.path))
        # Try download
        download_url = reverse("csvfile_download", kwargs={"pk": obj_id})
        download_resp = self.client.get(download_url)
        self.assertEqual(download_resp.status_code, 404)

    # Move file tests
    def test_researcher_can_move_file(self):
        self._login(self.researcher)
        # Upload file
        upload_resp = self._upload_csv("test.csv", b"col\nval\n")
        self.assertEqual(upload_resp.status_code, 201)
        obj_id = upload_resp.json()["id"]
        obj = CSV.objects.get(pk=obj_id)
        old_path = obj.file.path
        self.assertTrue(os.path.exists(old_path))
        # Move to new dir
        move_url = reverse("csvfile_move", kwargs={"pk": obj_id})
        move_resp = self.client.post(move_url, {"target_dir": "new_dir"})
        self.assertEqual(move_resp.status_code, 200)
        data = move_resp.json()
        self.assertEqual(data["id"], obj_id)
        self.assertIn("new_dir", data["file_path"])
        # Refresh obj
        obj.refresh_from_db()
        new_path = obj.file.path
        self.assertTrue(os.path.exists(new_path))
        self.assertFalse(os.path.exists(old_path))
        self.assertIn("new_dir", obj.file.name)

    def test_move_file_unauthenticated_forbidden(self):
        self._login(self.researcher)
        upload_resp = self._upload_csv()
        self.assertEqual(upload_resp.status_code, 201)
        obj_id = upload_resp.json()["id"]
        client2 = Client()
        move_url = reverse("csvfile_move", kwargs={"pk": obj_id})
        resp = client2.post(move_url, {"target_dir": "new"})
        self.assertEqual(resp.status_code, 403)

    def test_move_file_missing_target_dir_400(self):
        self._login(self.researcher)
        upload_resp = self._upload_csv()
        obj_id = upload_resp.json()["id"]
        move_url = reverse("csvfile_move", kwargs={"pk": obj_id})
        resp = self.client.post(move_url, {})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("target_dir is required", resp.json()["detail"])

    # Folder move tests
    def test_researcher_can_move_folder(self):
        self._login(self.researcher)
        # Create files in source dir
        upload1 = self._upload_csv("file1.csv")
        id1 = upload1.json()["id"]
        upload2 = self._upload_csv("file2.csv")
        id2 = upload2.json()["id"]
        # Manually move to source dir
        obj1 = CSV.objects.get(pk=id1)
        obj2 = CSV.objects.get(pk=id2)
        source_dir = "source_dir"
        # Create source dir
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir), exist_ok=True)
        # Move files
        old_path1 = obj1.file.path
        actual_filename1 = os.path.basename(obj1.file.name) if obj1.file else "file1.csv"
        new_path1 = os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir, actual_filename1)
        os.rename(old_path1, new_path1)
        obj1.file.name = f"datasets/csvs/{source_dir}/{actual_filename1}"
        obj1.save()
        old_path2 = obj2.file.path
        actual_filename2 = os.path.basename(obj2.file.name) if obj2.file else "file2.csv"
        new_path2 = os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir, actual_filename2)
        os.rename(old_path2, new_path2)
        obj2.file.name = f"datasets/csvs/{source_dir}/{actual_filename2}"
        obj2.save()
        # Now move folder
        move_resp = self.client.post(self.folder_move_url, {"source_dir": source_dir, "target_dir": "target_dir"})
        self.assertEqual(move_resp.status_code, 200)
        data = move_resp.json()
        self.assertIn("moved_files", data)
        self.assertEqual(len(data["moved_files"]), 2)
        self.assertIn(id1, data["moved_files"])
        self.assertIn(id2, data["moved_files"])
        # Check files moved
        obj1.refresh_from_db()
        obj2.refresh_from_db()
        self.assertIn("target_dir", obj1.file.name)
        self.assertIn("target_dir", obj2.file.name)
        self.assertTrue(os.path.exists(obj1.file.path))
        self.assertTrue(os.path.exists(obj2.file.path))
        self.assertFalse(os.path.exists(new_path1))
        self.assertFalse(os.path.exists(new_path2))

    def test_move_folder_unauthenticated_forbidden(self):
        resp = self.client.post(self.folder_move_url, {"source_dir": "src", "target_dir": "tgt"})
        self.assertEqual(resp.status_code, 403)

    def test_move_folder_no_files_404(self):
        self._login(self.researcher)
        resp = self.client.post(self.folder_move_url, {"source_dir": "empty", "target_dir": "target"})
        self.assertEqual(resp.status_code, 404)
        self.assertIn("No files found", resp.json()["detail"])

    def test_move_folder_missing_params_400(self):
        self._login(self.researcher)
        resp = self.client.post(self.folder_move_url, {"source_dir": "src"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("source_dir and target_dir are required", resp.json()["detail"])

    # Test cases for error handling in file moves
    def test_move_file_fails_does_not_update_db(self):
        self._login(self.researcher)
        # Upload file
        upload_resp = self._upload_csv("test.csv", b"col\nval\n")
        self.assertEqual(upload_resp.status_code, 201)
        obj_id = upload_resp.json()["id"]
        obj = CSV.objects.get(pk=obj_id)
        old_path = obj.file.path
        old_name = obj.file.name
        self.assertTrue(os.path.exists(old_path))
        # Simulate move failure by making target dir unwritable or file locked
        # For simplicity, we'll mock shutil.move to raise an exception
        import unittest.mock as mock
        with mock.patch('dataset.views.shutil.move', side_effect=OSError("Permission denied")):
            move_url = reverse("csvfile_move", kwargs={"pk": obj_id})
            move_resp = self.client.post(move_url, {"target_dir": "new_dir"})
            self.assertEqual(move_resp.status_code, 500)
            self.assertIn("Failed to move file", move_resp.json()["detail"])
            # Refresh obj and check DB not updated
            obj.refresh_from_db()
            self.assertEqual(obj.file.name, old_name)
            self.assertTrue(os.path.exists(old_path))  # File still in old location

    def test_move_folder_fails_does_not_update_db(self):
        self._login(self.researcher)
        # Create files in source dir
        upload1 = self._upload_csv("file1.csv")
        id1 = upload1.json()["id"]
        upload2 = self._upload_csv("file2.csv")
        id2 = upload2.json()["id"]
        # Manually move to source dir
        obj1 = CSV.objects.get(pk=id1)
        obj2 = CSV.objects.get(pk=id2)
        source_dir = "source_dir"
        # Create source dir
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir), exist_ok=True)
        # Move files
        old_path1 = obj1.file.path
        actual_filename1 = os.path.basename(obj1.file.name) if obj1.file else "file1.csv"
        new_path1 = os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir, actual_filename1)
        os.rename(old_path1, new_path1)
        obj1.file.name = f"datasets/csvs/{source_dir}/{actual_filename1}"
        obj1.save()
        old_path2 = obj2.file.path
        actual_filename2 = os.path.basename(obj2.file.name) if obj2.file else "file2.csv"
        new_path2 = os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir, actual_filename2)
        os.rename(old_path2, new_path2)
        obj2.file.name = f"datasets/csvs/{source_dir}/{actual_filename2}"
        obj2.save()
        # Now simulate move failure
        import unittest.mock as mock
        with mock.patch('dataset.views.shutil.move', side_effect=OSError("Disk full")):
            move_resp = self.client.post(self.folder_move_url, {"source_dir": source_dir, "target_dir": "target_dir"})
            self.assertEqual(move_resp.status_code, 500)
            self.assertIn("Failed to move file", move_resp.json()["detail"])
            # Check DB not updated
            obj1.refresh_from_db()
            obj2.refresh_from_db()
            self.assertIn(source_dir, obj1.file.name)
            self.assertIn(source_dir, obj2.file.name)
            self.assertTrue(os.path.exists(obj1.file.path))
            self.assertTrue(os.path.exists(obj2.file.path))

    # Permission edge-case tests
    def test_permission_user_not_found_returns_false(self):
        from .permissions import IsAuthenticatedAndVerified

        perm = IsAuthenticatedAndVerified()
        fake_request = SimpleNamespace()
        fake_request.session = {"user_id": "00000000-0000-0000-0000-000000000000", "username": "no_such_user"}
        self.assertFalse(perm.has_permission(fake_request, None))

    def test_permission_user_id_mismatch_returns_false(self):
        from .permissions import IsAuthenticatedAndVerified

        # Use existing researcher username but wrong session user_id
        perm = IsAuthenticatedAndVerified()
        fake_request = SimpleNamespace()
        fake_request.session = {"user_id": "11111111-1111-1111-1111-111111111111", "username": self.researcher.username}
        self.assertFalse(perm.has_permission(fake_request, None))

    # Serializer edge-case tests
    def test_serializer_get_file_url_value_error_returns_none(self):
        from .serializers import CSVFileSerializer

        class BadFile:
            @property
            def url(self):
                raise ValueError("no url")

        class Obj:
            file = BadFile()

        ser = CSVFileSerializer(context={})
        self.assertIsNone(ser.get_file_url(Obj()))

    def test_serializer_get_file_url_without_request_returns_url(self):
        from .serializers import CSVFileSerializer

        class GoodFile:
            def __init__(self):
                self.url = "/media/path/file.csv"

        class Obj:
            file = GoodFile()

        ser = CSVFileSerializer(context={})
        self.assertEqual(ser.get_file_url(Obj()), "/media/path/file.csv")

    def test_serializer_get_size_exception_returns_none(self):
        from .serializers import CSVFileSerializer

        class BadFile:
            @property
            def size(self):
                raise Exception("boom")

        class Obj:
            file = BadFile()

        ser = CSVFileSerializer(context={})
        self.assertIsNone(ser.get_size(Obj()))

    def test_serializer_get_directory_various_branches(self):
        from .serializers import CSVFileSerializer

        ser = CSVFileSerializer(context={})

        class ObjNone:
            file = None

        # file missing -> empty string
        self.assertEqual(ser.get_directory(ObjNone()), "")

        class ObjEmptyName:
            class F:
                name = ""
            file = F()

        self.assertEqual(ser.get_directory(ObjEmptyName()), "")

        class ObjOtherPath:
            class F:
                name = "other_prefix/file.csv"
            file = F()

        # path not starting with datasets/csvs/ -> empty
        self.assertEqual(ser.get_directory(ObjOtherPath()), "")

        class ObjWithSubdir:
            class F:
                name = "datasets/csvs/subdir1/subdir2/file.csv"
            file = F()

        # should return the directory part relative to datasets/csvs/
        actual = ser.get_directory(ObjWithSubdir())
        # normalize: remove any leading slashes and normalize separators for cross-platform comparison
        normalized = actual.lstrip('/\\').replace('/', os.path.sep).replace('\\', os.path.sep)
        self.assertEqual(normalized, os.path.join("subdir1", "subdir2"))

        class ObjRootFile:
            class F:
                name = "datasets/csvs/file.csv"
            file = F()

        # file directly under datasets/csvs -> empty string (normalize to handle leading slash)
        actual_root = ser.get_directory(ObjRootFile())
        normalized_root = actual_root.lstrip('/\\').replace('/', os.path.sep).replace('\\', os.path.sep)
        self.assertEqual(normalized_root, "")

    # Views edge-case tests
    def test_list_view_returns_raw_list_when_not_paginated(self):
        # Ensure paginate_queryset returns None so the final branch in list() is exercised
        from dataset import views as dataset_views

        self._login(self.researcher)
        # Upload one file so serializer.data is a list with one item
        upload_resp = self._upload_csv("listraw.csv")
        self.assertEqual(upload_resp.status_code, 201)

        with mock.patch.object(dataset_views.CSVFileListCreateView, 'paginate_queryset', return_value=None):
            resp = self.client.get(self.list_create_url)
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            # When not paginated, response should be a list
            self.assertIsInstance(data, list)
            self.assertTrue(any(isinstance(it, dict) and it.get('id') for it in data))

    def test_perform_destroy_ignores_storage_delete_exceptions(self):
        # Upload a file
        self._login(self.researcher)
        upload_resp = self._upload_csv("todelete.csv")
        self.assertEqual(upload_resp.status_code, 201)
        obj_id = upload_resp.json()["id"]
        obj = CSV.objects.get(pk=obj_id)
        file_path = obj.file.path
        # Patch default_storage.delete to raise
        with mock.patch('django.core.files.storage.default_storage.delete', side_effect=Exception("storage fail")):
            detail_url = reverse("csvfile_detail_destroy", kwargs={"pk": obj_id})
            del_resp = self.client.delete(detail_url)
            self.assertIn(del_resp.status_code, (200, 204))
            # DB record should be removed despite storage.delete failing
            self.assertFalse(CSV.objects.filter(pk=obj_id).exists())
            # File should still exist on disk because delete failed
            self.assertTrue(os.path.exists(file_path))
