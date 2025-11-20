# annotation/tests_mock_upload.py
from django.test import TestCase, RequestFactory
from unittest.mock import patch, MagicMock
from annotation.views import save_annotated_page
from annotation.models import Document
from django.core.files.uploadedfile import SimpleUploadedFile

class TestAnnotatedPageUploadMock(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.doc = Document.objects.create(
            source="pdf",
            content_url="x",
            payload_json={}
        )

    @patch("annotation.views._get_supabase")
    @patch("annotation.views._storage_upload_bytes")
    @patch("annotation.views._storage_public_or_signed_url")
    def test_upload_page_mock(
        self, mock_signed, mock_upload, mock_get
    ):
        fake_supabase = MagicMock()
        mock_get.return_value = fake_supabase
        mock_signed.return_value = "http://mocked-upload-url"

        fake_file = SimpleUploadedFile(
            "page.png", b"12345", content_type="image/png"
        )

        request = self.factory.post(
            f"/api/v1/documents/{self.doc.id}/annotated-page/?page=3",
            {"image": fake_file},
        )

        res = save_annotated_page(request, self.doc.id)
        self.assertEqual(res.status_code, 201)
        mock_upload.assert_called_once()
