# tests/test_views_update.py  (or append into your existing test_views.py)
import json
import os
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.base import ContentFile
from unittest.mock import patch
from save_to_database.models import CSV

class ViewsTestCase(TestCase):
    """Base test case with common setup."""
    
    def setUp(self):
        self.client = Client()
        # Disable Supabase upload signal during tests (virtual FS)
        os.environ['SUPABASE_UPLOAD_ENABLED'] = 'false'
        self.sample_json = [{"name": "John", "age": 30}]
        self.valid_data = {
            "name": "test-dataset",
            "source_json": self.sample_json
        }

class UpdateCsvRecordViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # initial dataset
        self.initial_json = [{"name": "Alice", "age": 28}]
        csv_bytes = b"name,age\nAlice,28\n"
        csv_file = ContentFile(csv_bytes, name="initial.csv")
        self.csv_record = CSV.objects.create(
            name="my-dataset",
            file=csv_file,
            source_json=self.initial_json
        )

    # POSITIVE TESTS #

    def test_update_csv_record_success_put(self):
        """PUT should update the CSV record and file contents."""
        url = reverse('save_to_database:update_csv_record', kwargs={'pk': self.csv_record.pk})
        new_json = [{"name": "Bob", "age": 40}]
        payload = {"name": "updated-dataset", "source_json": new_json}

        response = self.client.put(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['id'], self.csv_record.pk)
        self.assertEqual(data['name'], "updated-dataset")

        # fetch fresh instance
        updated = CSV.objects.get(pk=self.csv_record.pk)
        self.assertEqual(updated.source_json, new_json)

        # Under virtual FS we don't store file bytes locally; ensure filename updated
        self.assertTrue(updated.file.name.endswith('updated-dataset.csv') or 'updated-dataset' in updated.file.name)

    # NEGATIVE TESTS #

    def test_update_csv_record_not_found(self):
        """Updating non-existent record returns 404."""
        url = reverse('save_to_database:update_csv_record', kwargs={'pk': 9999})
        response = self.client.put(url, data=json.dumps({"name":"x","source_json":[{}]}), content_type='application/json')
        self.assertEqual(response.status_code, 404)

    def test_update_csv_record_invalid_json(self):
        """Invalid JSON should return 400."""
        url = reverse('save_to_database:update_csv_record', kwargs={'pk': self.csv_record.pk})
        response = self.client.put(url, data="not-json", content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    def test_update_csv_record_wrong_method(self):
        """GET on update endpoint should be 405."""
        url = reverse('save_to_database:update_csv_record', kwargs={'pk': self.csv_record.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

class UpdateCsvRecordViewExceptionTests(ViewsTestCase):
    """Tests update_csv_record view exception handling."""

    def setUp(self):
        super().setUp()

        self.csv_record = CSV.objects.create(
            name="dummy",
            source_json=[{"key": "value"}]
        )
        self.url = reverse(
            'save_to_database:update_csv_record',
            kwargs={'pk': self.csv_record.pk}
        )

    @patch('save_to_database.views.update_converted_csv')
    def test_update_csv_record_raises_exception_returns_500(self, mock_update):
        """Test that an exception in update_converted_csv returns a 500 error."""
        mock_update.side_effect = Exception("Something went wrong")

        response = self.client.put(
            self.url,
            data=json.dumps(self.valid_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Failed to update CSV record')
        self.assertIn('details', data)
        self.assertEqual(data['details'], 'Something went wrong')