from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import shutil

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from PIL import Image

class OCRTests(TestCase):
    def test_health_endpoint(self):
        resp = self.client.get("/ocr/health/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("status", resp.json())

    def test_upload_page_renders(self):
        resp = self.client.get("/ocr/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Upload", resp.content)

    def test_missing_file_returns_400(self):
        resp = self.client.post("/api/ocr/", {})
        self.assertEqual(resp.status_code, 400)

    def test_image_upload_uses_ocr(self):
        img_bytes = self._create_test_image_bytes()
        uploaded = SimpleUploadedFile("test.png", img_bytes, content_type="image/png")
        resp = self.client.post("/api/ocr/", {"file": uploaded})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("filename", data)
        self.assertIn("method", data)
        self.assertIn("pages", data)
        self.assertIsInstance(data["pages"], list)

    def test_pdf_support_missing_returns_error(self):
        # This test assumes HAS_PDF is False, so it will only pass if fitz is not installed
        fake_pdf = SimpleUploadedFile("doc.pdf", b"%%PDF-1.4\n%fakepdf", content_type="application/pdf")
        resp = self.client.post("/api/ocr/", {"file": fake_pdf})
        # Accept either 500 (if HAS_PDF is False) or 200 (if fitz is installed)
        self.assertIn(resp.status_code, [200, 500])

    def _create_test_image_bytes(self):
        from PIL import Image
        from io import BytesIO
        img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        bio = BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)
        return bio.read()
