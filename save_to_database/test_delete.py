from django.urls import reverse
from django.core.files.base import ContentFile
from django.test import TestCase, Client
from save_to_database.models import CSV


class DeleteCsvRecordTests(TestCase):
    """Tests for deleting CSV records"""

    def setUp(self):
        self.client = Client()

        self.csv_file = ContentFile(b"col1,col2\n1,2", name="test.csv")
        self.csv = CSV.objects.create(
            name="test_csv",
            file=self.csv_file,
            source_json=[{"col1": 1, "col2": 2}]
        )


        self.valid_delete_url = reverse(
            "save_to_database:delete_csv_record", args=[self.csv.id]
        )
        self.invalid_delete_url = reverse(
            "save_to_database:delete_csv_record", args=[self.csv.id + 100]
        )


    # POSITIVE TEST #
    def test_delete_existing_csv_record(self):
        """Deleting existing CSV record should return 200 and remove it"""
        response = self.client.delete(self.valid_delete_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CSV.objects.filter(id=self.csv.id).exists())


    # NEGATIVE TEST #
    def test_delete_nonexistent_csv_record(self):
        """Deleting non-existent CSV record should return 404"""
        response = self.client.delete(self.invalid_delete_url)
        self.assertEqual(response.status_code, 404)
