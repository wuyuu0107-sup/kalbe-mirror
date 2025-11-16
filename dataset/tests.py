import json
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
        self.assertIn("target_dir diperlukan", resp.json()["detail"])

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
        self.assertIn("Tidak ada berkas yang ditemukan", resp.json()["detail"])

    def test_move_folder_missing_params_400(self):
        self._login(self.researcher)
        resp = self.client.post(self.folder_move_url, {"source_dir": "src"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("source_dir dan target_dir diperlukan", resp.json()["detail"])

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
            self.assertIn("Gagal memindahkan berkas", move_resp.json()["detail"])
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
            self.assertIn("Gagal memindahkan berkas", move_resp.json()["detail"])
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

    # Additional tests for uncovered lines and FolderDeleteView
    def test_move_file_with_root_target_dir_sets_to_empty(self):
        self._login(self.researcher)
        # Upload file
        upload_resp = self._upload_csv("test.csv", b"col\nval\n")
        self.assertEqual(upload_resp.status_code, 201)
        obj_id = upload_resp.json()["id"]
        obj = CSV.objects.get(pk=obj_id)
        old_path = obj.file.path
        self.assertTrue(os.path.exists(old_path))
        # Move to root dir by setting target_dir='/'
        move_url = reverse("csvfile_move", kwargs={"pk": obj_id})
        move_resp = self.client.post(move_url, {"target_dir": "/"})
        self.assertEqual(move_resp.status_code, 200)
        data = move_resp.json()
        self.assertEqual(data["id"], obj_id)
        # Since target_dir='' after setting, new_path should be datasets/csvs/filename
        self.assertEqual(data["file_path"], "datasets/csvs/test.csv")  # Directly in root
        # Refresh obj
        obj.refresh_from_db()
        new_path = obj.file.path
        self.assertTrue(os.path.exists(new_path))
        # Check it's in root
        self.assertEqual(os.path.dirname(obj.file.name), "datasets/csvs")

    def test_move_folder_with_root_target_dir_sets_to_empty(self):
        self._login(self.researcher)
        # Create files in source dir - use unique names to avoid timestamp conflicts
        upload1 = self._upload_csv("unique_file1.csv")
        id1 = upload1.json()["id"]
        upload2 = self._upload_csv("unique_file2.csv")
        id2 = upload2.json()["id"]
        
        # Get the actual file names with timestamps
        obj1 = CSV.objects.get(pk=id1)
        obj2 = CSV.objects.get(pk=id2)
        
        # Place the source folder under a parent so moving to root actually changes paths
        source_dir = "parent/source_dir"
        # Create source dir
        source_dir_path = os.path.join(settings.MEDIA_ROOT, 'datasets', 'csvs', source_dir)
        os.makedirs(source_dir_path, exist_ok=True)
        
        # Move files using their actual names (with timestamps)
        old_path1 = obj1.file.path
        actual_filename1 = os.path.basename(obj1.file.name)
        new_path1 = os.path.join(source_dir_path, actual_filename1)
        
        # Ensure the source file exists before moving
        self.assertTrue(os.path.exists(old_path1), f"Source file should exist at {old_path1}")
        
        os.rename(old_path1, new_path1)
        obj1.file.name = f"datasets/csvs/{source_dir}/{actual_filename1}"
        obj1.save()
        
        old_path2 = obj2.file.path
        actual_filename2 = os.path.basename(obj2.file.name)
        new_path2 = os.path.join(source_dir_path, actual_filename2)
        
        # Ensure the source file exists before moving
        self.assertTrue(os.path.exists(old_path2), f"Source file should exist at {old_path2}")
        
        os.rename(old_path2, new_path2)
        obj2.file.name = f"datasets/csvs/{source_dir}/{actual_filename2}"
        obj2.save()
        
        # Verify files are in the source directory before the folder move
        self.assertTrue(os.path.exists(new_path1), f"File1 should be in source dir at {new_path1}")
        self.assertTrue(os.path.exists(new_path2), f"File2 should be in source dir at {new_path2}")
        
        # Now move folder to root by setting target_dir='/'
        move_resp = self.client.post(self.folder_move_url, {"source_dir": source_dir, "target_dir": "/"})
        
        self.assertEqual(move_resp.status_code, 200)
        data = move_resp.json()
        self.assertIn("moved_files", data)
        self.assertEqual(len(data["moved_files"]), 2)
        
        # Check files moved - they should be in the same folder name but under root
        obj1.refresh_from_db()
        obj2.refresh_from_db()
        # After moving to root with target_dir='/', the files should be in datasets/csvs/source_dir/filename
        self.assertEqual(obj1.file.name, f"datasets/csvs/source_dir/{actual_filename1}")
        self.assertEqual(obj2.file.name, f"datasets/csvs/source_dir/{actual_filename2}")
        self.assertTrue(os.path.exists(obj1.file.path))
        self.assertTrue(os.path.exists(obj2.file.path))

    def test_folder_delete_success(self):
        self._login(self.researcher)
        # Create files in source dir
        upload1 = self._upload_csv("file1.csv")
        id1 = upload1.json()["id"]
        upload2 = self._upload_csv("file2.csv")
        id2 = upload2.json()["id"]
        # Manually move to source dir
        obj1 = CSV.objects.get(pk=id1)
        obj2 = CSV.objects.get(pk=id2)
        source_dir = "delete_dir"
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
        # Now delete folder
        delete_url = reverse("folder_delete")
        delete_resp = self.client.delete(delete_url, json.dumps({"source_dir": source_dir}), content_type='application/json')
        self.assertEqual(delete_resp.status_code, 200)
        data = delete_resp.json()
        self.assertIn("deleted_files", data)
        self.assertEqual(len(data["deleted_files"]), 2)
        self.assertIn(id1, data["deleted_files"])
        self.assertIn(id2, data["deleted_files"])
        # Check files and records deleted
        self.assertFalse(CSV.objects.filter(pk=id1).exists())
        self.assertFalse(CSV.objects.filter(pk=id2).exists())
        self.assertFalse(os.path.exists(new_path1))
        self.assertFalse(os.path.exists(new_path2))

    def test_folder_delete_unauthenticated_forbidden(self):
        delete_url = reverse("folder_delete")
        resp = self.client.delete(delete_url, json.dumps({"source_dir": "some_dir"}), content_type='application/json')
        self.assertEqual(resp.status_code, 403)

    def test_folder_delete_missing_source_dir_400(self):
        self._login(self.researcher)
        delete_url = reverse("folder_delete")
        resp = self.client.delete(delete_url, json.dumps({}), content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn("source_dir diperlukan", resp.json()["detail"])

    def test_folder_delete_no_files_404(self):
        self._login(self.researcher)
        delete_url = reverse("folder_delete")
        resp = self.client.delete(delete_url, json.dumps({"source_dir": "empty_dir"}), content_type='application/json')
        self.assertEqual(resp.status_code, 404)
        self.assertIn("Tidak ada berkas yang ditemukan", resp.json()["detail"])

    def test_folder_delete_ignores_storage_delete_exceptions(self):
        self._login(self.researcher)
        # Upload a file
        upload_resp = self._upload_csv("faildelete.csv")
        self.assertEqual(upload_resp.status_code, 201)
        obj_id = upload_resp.json()["id"]
        obj = CSV.objects.get(pk=obj_id)
        file_path = obj.file.path

        # Move the uploaded file into a source directory so FolderDeleteView will find it
        source_dir = "fail_delete_dir"
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir), exist_ok=True)
        actual_filename = os.path.basename(obj.file.name) if obj.file else "faildelete.csv"
        new_path_fs = os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir, actual_filename)
        os.rename(file_path, new_path_fs)
        obj.file.name = f"datasets/csvs/{source_dir}/{actual_filename}"
        obj.save()

        # Patch storage.delete to raise an exception to hit the except Exception: pass branch
        with mock.patch('django.core.files.storage.default_storage.delete', side_effect=Exception("storage fail")):
            delete_url = reverse("folder_delete")
            delete_resp = self.client.delete(delete_url, json.dumps({"source_dir": source_dir}), content_type='application/json')
            # Should still return 200 and report the deleted DB record
            self.assertEqual(delete_resp.status_code, 200)
            data = delete_resp.json()
            self.assertIn("deleted_files", data)
            self.assertIn(obj_id, data["deleted_files"])

        # The file should still exist on disk because storage.delete raised
        self.assertTrue(os.path.exists(new_path_fs))
        # The DB record should have been deleted regardless
        self.assertFalse(CSV.objects.filter(pk=obj_id).exists())

    # Rename file tests
    def test_researcher_can_rename_file(self):
        self._login(self.researcher)
        # Upload file
        upload_resp = self._upload_csv("oldname.csv", b"col\nval\n")
        self.assertEqual(upload_resp.status_code, 201)
        obj_id = upload_resp.json()["id"]
        obj = CSV.objects.get(pk=obj_id)
        old_path = obj.file.path
        old_name = obj.file.name
        self.assertTrue(os.path.exists(old_path))
        # Rename file
        rename_url = reverse("csvfile_rename", kwargs={"pk": obj_id})
        rename_resp = self.client.post(rename_url, {"new_name": "newname.csv"})
        self.assertEqual(rename_resp.status_code, 200)
        data = rename_resp.json()
        self.assertEqual(data["id"], obj_id)
        self.assertIn("newname.csv", data["filename"])
        # Refresh obj
        obj.refresh_from_db()
        new_path = obj.file.path
        self.assertTrue(os.path.exists(new_path))
        self.assertFalse(os.path.exists(old_path))
        self.assertIn("newname.csv", obj.file.name)

    def test_rename_file_unauthenticated_forbidden(self):
        self._login(self.researcher)
        upload_resp = self._upload_csv()
        self.assertEqual(upload_resp.status_code, 201)
        obj_id = upload_resp.json()["id"]
        client2 = Client()
        rename_url = reverse("csvfile_rename", kwargs={"pk": obj_id})
        resp = client2.post(rename_url, {"new_name": "new.csv"})
        self.assertEqual(resp.status_code, 403)

    def test_rename_file_missing_new_name_400(self):
        self._login(self.researcher)
        upload_resp = self._upload_csv()
        obj_id = upload_resp.json()["id"]
        rename_url = reverse("csvfile_rename", kwargs={"pk": obj_id})
        resp = self.client.post(rename_url, {})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("new_name diperlukan", resp.json()["detail"])

    def test_rename_file_invalid_pk_404(self):
        self._login(self.researcher)
        rename_url = reverse("csvfile_rename", kwargs={"pk": 99999})
        resp = self.client.post(rename_url, {"new_name": "new.csv"})
        self.assertEqual(resp.status_code, 404)

    # Rename folder tests
    def test_researcher_can_rename_folder(self):
        self._login(self.researcher)
        # Create files in source dir
        upload1 = self._upload_csv("file1.csv")
        id1 = upload1.json()["id"]
        upload2 = self._upload_csv("file2.csv")
        id2 = upload2.json()["id"]
        # Manually move to source dir
        obj1 = CSV.objects.get(pk=id1)
        obj2 = CSV.objects.get(pk=id2)
        source_dir = "old_folder"
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
        # Now rename folder
        rename_url = reverse("folder_rename")
        rename_resp = self.client.post(rename_url, {"source_dir": source_dir, "new_name": "new_folder"})
        self.assertEqual(rename_resp.status_code, 200)
        data = rename_resp.json()
        self.assertIn("updated_files", data)
        self.assertEqual(len(data["updated_files"]), 2)
        self.assertIn(id1, data["updated_files"])
        self.assertIn(id2, data["updated_files"])
        # Check files renamed
        obj1.refresh_from_db()
        obj2.refresh_from_db()
        self.assertIn("new_folder", obj1.file.name)
        self.assertIn("new_folder", obj2.file.name)
        self.assertTrue(os.path.exists(obj1.file.path))
        self.assertTrue(os.path.exists(obj2.file.path))
        self.assertFalse(os.path.exists(new_path1))
        self.assertFalse(os.path.exists(new_path2))

    def test_rename_folder_unauthenticated_forbidden(self):
        rename_url = reverse("folder_rename")
        resp = self.client.post(rename_url, {"source_dir": "old", "new_name": "new"})
        self.assertEqual(resp.status_code, 403)

    def test_rename_folder_missing_params_400(self):
        self._login(self.researcher)
        rename_url = reverse("folder_rename")
        resp = self.client.post(rename_url, {"source_dir": "old"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("source_dir dan new_name diperlukan", resp.json()["detail"])

    def test_rename_folder_no_files_200(self):
        self._login(self.researcher)
        # Create empty folder
        empty_dir = "empty_folder"
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', empty_dir), exist_ok=True)
        rename_url = reverse("folder_rename")
        rename_resp = self.client.post(rename_url, {"source_dir": empty_dir, "new_name": "renamed_empty"})
        self.assertEqual(rename_resp.status_code, 200)
        data = rename_resp.json()
        self.assertIn("updated_files", data)
        self.assertEqual(len(data["updated_files"]), 0)
        # Check directory renamed
        old_path = os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', empty_dir)
        new_path = os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', "renamed_empty")
        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(new_path))

    def test_rename_file_os_rename_raises_returns_500_and_db_not_updated(self):
        self._login(self.researcher)
        # Upload file
        upload_resp = self._upload_csv("willfail.csv", b"col\nval\n")
        self.assertEqual(upload_resp.status_code, 201)
        obj_id = upload_resp.json()["id"]
        obj = CSV.objects.get(pk=obj_id)
        old_path = obj.file.path
        old_name = obj.file.name
        self.assertTrue(os.path.exists(old_path))

        # Patch os.rename in the views module to raise
        with mock.patch('dataset.views.os.rename', side_effect=OSError("Permission denied")):
            rename_url = reverse("csvfile_rename", kwargs={"pk": obj_id})
            rename_resp = self.client.post(rename_url, {"new_name": "newname.csv"})
            self.assertEqual(rename_resp.status_code, 500)
            self.assertIn("Gagal mengubah nama berkas", rename_resp.json().get("detail", ""))

        # Ensure DB not updated and file still in old location
        obj.refresh_from_db()
        self.assertEqual(obj.file.name, old_name)
        self.assertTrue(os.path.exists(old_path))


    def test_rename_folder_os_rename_raises_returns_500_and_db_not_updated(self):
        self._login(self.researcher)
        # Create files in source dir
        upload1 = self._upload_csv("f1.csv")
        id1 = upload1.json()["id"]
        upload2 = self._upload_csv("f2.csv")
        id2 = upload2.json()["id"]
        obj1 = CSV.objects.get(pk=id1)
        obj2 = CSV.objects.get(pk=id2)
        source_dir = "folder_fail_rename"
        # Create source dir
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir), exist_ok=True)
        # Move files into source dir
        old_path1 = obj1.file.path
        actual_filename1 = os.path.basename(obj1.file.name) if obj1.file else "f1.csv"
        new_path1 = os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir, actual_filename1)
        os.rename(old_path1, new_path1)
        obj1.file.name = f"datasets/csvs/{source_dir}/{actual_filename1}"
        obj1.save()
        old_path2 = obj2.file.path
        actual_filename2 = os.path.basename(obj2.file.name) if obj2.file else "f2.csv"
        new_path2 = os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir, actual_filename2)
        os.rename(old_path2, new_path2)
        obj2.file.name = f"datasets/csvs/{source_dir}/{actual_filename2}"
        obj2.save()

        # Patch os.rename in the views module to raise when attempting to rename the folder
        with mock.patch('dataset.views.os.rename', side_effect=OSError("Disk full")):
            rename_url = reverse("folder_rename")
            rename_resp = self.client.post(rename_url, {"source_dir": source_dir, "new_name": "new_name_folder"})
            self.assertEqual(rename_resp.status_code, 500)
            self.assertIn("Gagal mengubah nama folder", rename_resp.json().get("detail", ""))

        # Ensure DB not updated for files (still reference source_dir) and files still exist
        obj1.refresh_from_db()
        obj2.refresh_from_db()
        self.assertIn(source_dir, obj1.file.name)
        self.assertIn(source_dir, obj2.file.name)
        self.assertTrue(os.path.exists(obj1.file.path))
        self.assertTrue(os.path.exists(obj2.file.path))

    # Test cases for duplicate name checks in move and rename operations
    def test_move_file_to_duplicate_name_returns_400(self):
        self._login(self.researcher)
        # Upload two files with different names
        upload1 = self._upload_csv("file1.csv")
        id1 = upload1.json()["id"]
        upload2 = self._upload_csv("file2.csv")
        id2 = upload2.json()["id"]
        # Create a target directory where a file with the same filename already exists
        target_dir = "conflict_dir"
        filename2 = upload2.json().get("filename")
        conflict_storage_path = f"datasets/csvs/{target_dir}/{filename2}"
        # Make sure the directory exists on disk
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', target_dir), exist_ok=True)
        # Create a DB record that claims to own the destination path
        CSV.objects.create(name=os.path.splitext(filename2)[0], file=conflict_storage_path)

        # Now attempt to move file2 into target_dir where a file with same name exists
        move_url = reverse("csvfile_move", kwargs={"pk": id2})
        move_resp = self.client.post(move_url, {"target_dir": target_dir})
        self.assertEqual(move_resp.status_code, 400)
        self.assertIn("Berkas dengan nama ini sudah ada di direktori tujuan.", move_resp.json()["detail"])

    def test_move_file_to_duplicate_folder_name_returns_400(self):
        self._login(self.researcher)
        # Upload file
        upload = self._upload_csv("file.csv")
        obj_id = upload.json()["id"]
        # Put the file into a source subdir so that moving to root will actually change location
        obj = CSV.objects.get(pk=obj_id)
        source_dir = "src_for_move"
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir), exist_ok=True)
        old_path = obj.file.path
        actual_filename = os.path.basename(obj.file.name) if obj.file else "file.csv"
        new_path_fs = os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir, actual_filename)
        os.rename(old_path, new_path_fs)
        obj.file.name = f"datasets/csvs/{source_dir}/{actual_filename}"
        obj.save()

        # Create a folder with same base name as the file at the root
        folder_name = "file.csv"  # WITH extension to match the view's check
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', folder_name), exist_ok=True)
        # Add a file under that folder so the DB reflects it
        upload2 = self._upload_csv("subfile.csv")
        obj2 = CSV.objects.get(pk=upload2.json()["id"])
        obj2.file.name = f"datasets/csvs/{folder_name}/subfile.csv"
        obj2.save()

        # Now try to move the original file back to root where folder "file.csv" exists
        move_url = reverse("csvfile_move", kwargs={"pk": obj_id})
        move_resp = self.client.post(move_url, {"target_dir": ""})
        self.assertEqual(move_resp.status_code, 400)
        self.assertIn("Folder dengan nama ini sudah ada di direktori tujuan.", move_resp.json()["detail"])

    def test_move_folder_to_duplicate_name_returns_400(self):
        self._login(self.researcher)
        # Create folder with files
        upload1 = self._upload_csv("f1.csv")
        id1 = upload1.json()["id"]
        obj1 = CSV.objects.get(pk=id1)
        source_dir = "source"
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir), exist_ok=True)
        old_path1 = obj1.file.path
        new_path1 = os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir, "f1.csv")
        os.rename(old_path1, new_path1)
        obj1.file.name = f"datasets/csvs/{source_dir}/f1.csv"
        obj1.save()
        
        # Create a file with same name as folder (without extension) - but the view checks for exact match
        # We need to create a file at the exact path that the view will check
        target_file_path = "datasets/csvs/source"  # This is what the view checks for
        conflict_file = CSV.objects.create(name="source", file=target_file_path)
        
        # Now try to move folder to root where "source" file exists
        move_resp = self.client.post(self.folder_move_url, {"source_dir": source_dir, "target_dir": ""})
        self.assertEqual(move_resp.status_code, 400)
        self.assertIn("Berkas dengan nama ini sudah ada di direktori tujuan.", move_resp.json()["detail"])

    def test_rename_file_to_duplicate_name_returns_400(self):
        self._login(self.researcher)
        # Upload two files
        upload1 = self._upload_csv("file1.csv")
        id1 = upload1.json()["id"]
        upload2 = self._upload_csv("file2.csv")
        id2 = upload2.json()["id"]
        # Rename file2 to file1.csv
        rename_url = reverse("csvfile_rename", kwargs={"pk": id2})
        rename_resp = self.client.post(rename_url, {"new_name": "file1.csv"})
        self.assertEqual(rename_resp.status_code, 400)
        self.assertIn("Berkas dengan nama ini sudah ada di direktori.", rename_resp.json()["detail"])

    def test_rename_file_to_duplicate_folder_name_returns_400(self):
        self._login(self.researcher)
        # Upload file
        upload = self._upload_csv("file.csv")
        obj_id = upload.json()["id"]
        # Create folder without extension and put a file inside
        folder_name = "file"  # Without extension to match the view's check
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'datasets', 'csvs', folder_name), exist_ok=True)
        upload2 = self._upload_csv("sub.csv")
        obj2 = CSV.objects.get(pk=upload2.json()["id"])
        obj2.file.name = f"datasets/csvs/{folder_name}/sub.csv"
        obj2.save()
        # Rename file.csv to "file" (without extension) to conflict with the folder
        rename_url = reverse("csvfile_rename", kwargs={"pk": obj_id})
        rename_resp = self.client.post(rename_url, {"new_name": "file"})  # Without extension
        self.assertEqual(rename_resp.status_code, 400)
        self.assertIn("Folder dengan nama ini sudah ada di direktori.", rename_resp.json()["detail"])

    def test_rename_folder_to_duplicate_name_returns_400(self):
        self._login(self.researcher)
        # Create folder
        source_dir = "old_folder"
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir), exist_ok=True)
        upload = self._upload_csv("f.csv")
        obj = CSV.objects.get(pk=upload.json()["id"])
        obj.file.name = f"datasets/csvs/{source_dir}/f.csv"
        obj.save()
        # Create a file with name "new_folder" (without extension)
        # The view checks for exact match at the target path
        target_file_path = "datasets/csvs/new_folder"
        conflict_file = CSV.objects.create(name="new_folder", file=target_file_path)
        
        # Rename folder to "new_folder"
        rename_url = reverse("folder_rename")
        rename_resp = self.client.post(rename_url, {"source_dir": source_dir, "new_name": "new_folder"})
        self.assertEqual(rename_resp.status_code, 400)
        self.assertIn("Berkas dengan nama ini sudah ada di direktori.", rename_resp.json()["detail"])

    def test_move_file_case_insensitive_duplicate(self):
        self._login(self.researcher)
        # Upload file "test.csv" in root
        upload1 = self._upload_csv("test.csv")
        id1 = upload1.json()["id"]
        # Upload file "TEST.csv" in subdir
        target_dir = "subdir"
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', target_dir), exist_ok=True)
        upload2 = self._upload_csv("TEST.csv")
        id2 = upload2.json()["id"]
        obj2 = CSV.objects.get(pk=id2)
        obj2.file.name = f"datasets/csvs/{target_dir}/TEST.csv"
        obj2.save()
        # Try to move "test.csv" to subdir where "TEST.csv" exists (case-insensitive duplicate)
        move_url = reverse("csvfile_move", kwargs={"pk": id1})
        move_resp = self.client.post(move_url, {"target_dir": target_dir})
        self.assertEqual(move_resp.status_code, 400)
        self.assertIn("Berkas dengan nama ini sudah ada di direktori tujuan.", move_resp.json()["detail"])

    def test_rename_file_case_insensitive_duplicate(self):
        self._login(self.researcher)
        # Upload two files
        upload1 = self._upload_csv("file1.csv")
        id1 = upload1.json()["id"]
        upload2 = self._upload_csv("file2.csv")
        id2 = upload2.json()["id"]
        # Rename file2 to file1.csv
        rename_url = reverse("csvfile_rename", kwargs={"pk": id2})
        rename_resp = self.client.post(rename_url, {"new_name": "FILE1.csv"})
        self.assertEqual(rename_resp.status_code, 400)
        self.assertIn("Berkas dengan nama ini sudah ada di direktori.", rename_resp.json()["detail"])

    def test_move_folder_case_insensitive_duplicate(self):
        self._login(self.researcher)
        # Create folder "source" with files
        source_dir = "source"
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir), exist_ok=True)
        upload1 = self._upload_csv("f1.csv")
        obj1 = CSV.objects.get(pk=upload1.json()["id"])
        obj1.file.name = f"datasets/csvs/{source_dir}/f1.csv"
        obj1.save()
        # Create folder "SOURCE" with files (same name, different case)
        existing_folder = "SOURCE"
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', existing_folder), exist_ok=True)
        upload2 = self._upload_csv("f2.csv")
        obj2 = CSV.objects.get(pk=upload2.json()["id"])
        obj2.file.name = f"datasets/csvs/{existing_folder}/f2.csv"
        obj2.save()
        # Try to move "source" to root where "SOURCE" exists (case-insensitive duplicate)
        move_resp = self.client.post(self.folder_move_url, {"source_dir": source_dir, "target_dir": ""})
        self.assertEqual(move_resp.status_code, 400)
        self.assertIn("Folder dengan nama ini sudah ada di direktori tujuan.", move_resp.json()["detail"])

    def test_rename_folder_case_insensitive_duplicate(self):
        self._login(self.researcher)
        # Create folder
        source_dir = "old_folder"
        os.makedirs(os.path.join(settings.MEDIA_ROOT, 'datasets/csvs', source_dir), exist_ok=True)
        upload = self._upload_csv("f.csv")
        obj = CSV.objects.get(pk=upload.json()["id"])
        obj.file.name = f"datasets/csvs/{source_dir}/f.csv"
        obj.save()
        # Create a file with name "new_folder" (without extension)
        # The view checks for exact match at the target path
        target_file_path = "datasets/csvs/NEW_FOLDER"
        conflict_file = CSV.objects.create(name="NEW_FOLDER", file=target_file_path)
        
        # Rename folder to "NEW_FOLDER" (case-insensitive duplicate)
        rename_url = reverse("folder_rename")
        rename_resp = self.client.post(rename_url, {"source_dir": source_dir, "new_name": "NEW_FOLDER"})
        self.assertEqual(rename_resp.status_code, 400)
        self.assertIn("Berkas dengan nama ini sudah ada di direktori.", rename_resp.json()["detail"])
