# annotation/tests_mock_supabase.py
from django.test import TestCase, RequestFactory
from unittest.mock import patch, MagicMock
from annotation.views import save_annotated_page
from annotation.models import Document
from django.core.files.uploadedfile import SimpleUploadedFile

class TestSupabaseUploadMock(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.doc = Document.objects.create(
            source="pdf",
            content_url="http://test/file.pdf",
            payload_json={}
        )

    @patch("annotation.views._get_supabase")
    @patch("annotation.views._storage_public_or_signed_url")
    @patch("annotation.views._storage_upload_bytes")
    def test_supabase_upload_mocked(
        self, mock_upload, mock_signed_url, mock_get_supabase
    ):
        # --- Stub Supabase client ---
        fake_supabase = MagicMock()
        mock_get_supabase.return_value = fake_supabase

        # --- Stub return values ---
        mock_signed_url.return_value = "https://mocked-public-url.com/image.png"

        # --- Fake PNG upload ---
        fake_file = SimpleUploadedFile(
            "test.png", b"fake-image-bytes", content_type="image/png"
        )
        request = self.factory.post(
            f"/api/v1/documents/{self.doc.id}/annotated-page/?page=1",
            {"image": fake_file}
        )

        response = save_annotated_page(request, self.doc.id)

        self.assertEqual(response.status_code, 201)
        mock_upload.assert_called_once()
        mock_signed_url.assert_called_once()
