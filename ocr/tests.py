from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import shutil

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from PIL import Image

class OCRTests(TestCase):
    def _create_test_image_bytes(self, text="Hello World"):
        """Create a small in-memory PNG image and return its bytes."""
        # For the purposes of these unit tests we don't render the provided
        # text into the image (that would require font handling). Instead
        # we create a plain image and rely on mocking pytesseract to return
        # the expected text for each test case. This keeps tests fast and
        # deterministic without external font/renderer dependencies.
        img = Image.new("RGB", (300, 100), color=(255, 255, 255))
        bio = BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)
        return bio.read()

    def test_upload_page_renders(self):
        """GET / should return 200 and contain the upload form."""
        resp = self.client.get("/")
        # URLConf mounts upload_page at root, ensure 200
        self.assertEqual(resp.status_code, 200)

    def test_health_endpoint(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertJSONEqual(resp.content, {"ok": True})

    @patch("ocr.views.pytesseract.image_to_data")
    @patch("ocr.views.pytesseract.image_to_string")
    def test_image_upload_uses_ocr(self, mock_to_string, mock_to_data):
        """POST an image file and ensure OCR was called and JSON returned."""
        # Mock tesseract outputs
        mock_to_string.return_value = "Detected text"
        mock_to_data.return_value = {"conf": ["95", "-1", "88"]}

        img_bytes = self._create_test_image_bytes()
        uploaded = SimpleUploadedFile("test.png", img_bytes, content_type="image/png")

        resp = self.client.post("/api/ocr", {"file": uploaded})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["filename"], "test.png")
        self.assertEqual(data["method"], "ocr")
        self.assertIn("pages", data)
        self.assertEqual(data["pages"][0]["text"], "Detected text")

    # Real-fixture based tests --------------------------------------------------
    def _fixture_bytes_or_skip(self, name: str):
        fixtures = Path(__file__).resolve().parent / "test_files"
        path = fixtures / name
        if not path.exists():
            self.skipTest(f"Fixture not found: {path}")
        return path.read_bytes()

    def test_missing_file_returns_400(self):
        resp = self.client.post("/api/ocr", {})
        self.assertEqual(resp.status_code, 400)

    @patch("ocr.views.HAS_PDF", False)
    def test_pdf_support_missing_returns_error(self):
        # craft a fake pdf upload
        fake_pdf = SimpleUploadedFile("doc.pdf", b"%%PDF-1.4\n%fakepdf", content_type="application/pdf")
        resp = self.client.post("/api/ocr", {"file": fake_pdf})
        # When HAS_PDF is False, view returns 500 with json error
        self.assertEqual(resp.status_code, 500)
        self.assertIn("error", resp.json())
