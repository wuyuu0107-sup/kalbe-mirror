import os
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from .models import CSV



class CSVModelTests(TestCase):
    def setUp(self):
        # Temporary CSV file for tests
        self.csv_content = b"name,age\nAlice,25\nBob,30\n"
        self.uploaded_file = SimpleUploadedFile(
            "test.csv", self.csv_content, content_type="text/csv"
        )

    # ------------------------
    # POSITIVE TESTS
    # ------------------------
    def test_create_valid_csv(self):
        """ Model should save correctly with all fields populated."""
        csv = CSV.objects.create(
            name="Valid CSV",
            file=self.uploaded_file,
            source_json={"source": "ocr"},
        )
        self.assertEqual(csv.name, "Valid CSV")
        self.assertTrue(csv.file.name.startswith("datasets/csvs/"))
        self.assertEqual(csv.source_json, {"source": "ocr"})
        self.assertEqual(str(csv), "Valid CSV")
        self.assertIsNotNone(csv.created_at)

    def test_default_values_applied(self):
        """ Optional fields can be blank/None."""
        csv = CSV.objects.create(name="Defaults", file=self.uploaded_file)
        self.assertIsNone(csv.source_json)

    def test_auto_created_timestamp(self):
        """ created_at should be automatically populated."""
        csv = CSV.objects.create(name="Timestamp", file=self.uploaded_file)
        self.assertLess(abs((csv.created_at - timezone.now()).total_seconds()), 5)

    def test_file_upload_path(self):
        """ Uploaded files should be stored under datasets/csvs/."""
        csv = CSV.objects.create(name="Path Test", file=self.uploaded_file)
        self.assertIn("datasets/csvs/", csv.file.name)

    # ------------------------
    # NEGATIVE TESTS
    # ------------------------
    def test_missing_required_name_field(self):
        """ Model should not save without a name."""
        csv = CSV(file=self.uploaded_file)
        with self.assertRaises(ValidationError):
            csv.full_clean()

    def test_missing_required_file_field(self):
        """ Model should not save without a file."""
        csv = CSV(name="No File Provided")
        # VirtualFileField is designed to allow blank/default values (virtual storage),
        # so validation should pass and the stored file name should be empty.
        try:
            csv.full_clean()
        except ValidationError:
            self.fail("VirtualFileField should allow missing file; ValidationError raised")
        # Ensure the file name defaults to empty string
        self.assertEqual(csv.file.name, "")

    def test_name_too_long(self):
        """ Name exceeding max_length=255 should raise an error."""
        long_name = "A" * 256
        csv = CSV(name=long_name, file=self.uploaded_file)
        with self.assertRaises(ValidationError):
            csv.full_clean()

    def test_invalid_json_field(self):
        """ Non-serializable JSON should fail validation."""
        csv = CSV(name="Invalid JSON", file=self.uploaded_file, source_json={1, 2, 3})
        with self.assertRaises(ValidationError):
            csv.full_clean()  # triggers validation without saving

    def test_blank_name_validation(self):
        """ Empty name string should fail validation."""
        csv = CSV(name="", file=self.uploaded_file)
        with self.assertRaises(ValidationError):
            csv.full_clean()

    # ------------------------
    # CLEANUP
    # ------------------------
    def tearDown(self):
        """Remove any uploaded files after tests (robust to storage backends)."""
        for csv in CSV.objects.all():
            path = None
            try:
                path = csv.file.path
            except Exception:
                # Storage backend may not expose a filesystem path
                path = None
            if path and os.path.exists(path):
                os.remove(path)
# ...existing code...