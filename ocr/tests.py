from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase


class OCRTests(TestCase):
    def test_health_endpoint(self):
        resp = self.client.get("/ocr/health/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("status", resp.json())

    def test_upload_page_renders(self):
        resp = self.client.get("/ocr/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Upload", resp.content)

    def test_missing_file_returns_error(self):
        # view returns JSON with success False and an error message when pdf or API key missing
        resp = self.client.post("/ocr/", {})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, dict)
        self.assertIn("success", data)
        self.assertFalse(data["success"])
        self.assertIn("error", data)


    def test_pdf_support_missing_returns_error(self):
        # If the system doesn't have PyMuPDF or API key, posting a PDF without API key yields error
        fake_pdf = b"%PDF-1.4\n%EOF\n"
        uploaded = SimpleUploadedFile("test.pdf", fake_pdf, content_type="application/pdf")
        resp = self.client.post("/ocr/", {"pdf": uploaded})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("success", data)
        self.assertFalse(data["success"])
        self.assertIn("error", data)
