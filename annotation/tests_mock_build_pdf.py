# annotation/tests_mock_build_pdf.py
from django.test import TestCase, RequestFactory
from unittest.mock import patch, MagicMock
from annotation.views import build_annotated_pdf
from annotation.models import Document

class TestBuildAnnotatedPDFMock(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.doc = Document.objects.create(
            source="pdf",
            content_url="url",
            payload_json={},
            meta={
                "annotated_pages": {
                    "1": "http://image1",
                    "2": "http://image2"
                }
            }
        )

    @patch("annotation.views._get_supabase")
    @patch("annotation.views._storage_upload_bytes")
    @patch("annotation.views._storage_public_or_signed_url")
    @patch("annotation.views.img2pdf.convert")
    @patch("annotation.views.requests.get")
    def test_build_pdf_with_mocks(
        self, mock_get, mock_convert, mock_signed, mock_upload, mock_supabase
    ):
        # stub image downloads
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"fake-png"

        # stub convert to pdf
        mock_convert.return_value = b"%PDF-fake"

        # stub supabase
        fake_supabase = MagicMock()
        mock_supabase.return_value = fake_supabase
        mock_signed.return_value = "http://mocked-pdf-url"

        request = self.factory.post(f"/api/v1/documents/{self.doc.id}/build-annotated-pdf/")
        response = build_annotated_pdf(request, self.doc.id)

        self.assertEqual(response.status_code, 201)
        mock_convert.assert_called_once()
        self.assertIn("annotated_pdf_url", response.data)
