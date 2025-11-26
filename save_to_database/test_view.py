import json
from django.test import TestCase, Client
from django.urls import reverse
from unittest.mock import patch, MagicMock
from .models import CSV


class ViewsTestCase(TestCase):
    """Base test case with common setup."""
    
    def setUp(self):
        self.client = Client()
        self.sample_json = [{"name": "John", "age": 30}]
        self.valid_data = {
            "name": "test-dataset",
            "source_json": self.sample_json
        }



class SaveConvertedCsvFunctionTests(ViewsTestCase):
    """Test the save_converted_csv utility function."""
    
    def test_save_converted_csv_creates_record(self):
        """Should create CSV record with correct data."""
        from .views import save_converted_csv
        
        json_data = [
            {"name": "John", "age": 30},
            {"name": "Jane", "age": 25}
        ]
        
        dataset = save_converted_csv("test-function", json_data)
        
        # Verify record creation
        self.assertEqual(dataset.name, "test-function")
        self.assertEqual(dataset.source_json, json_data)
        self.assertTrue(dataset.file.name.endswith('.csv'))
        
        # Verify CSV content
        dataset.file.seek(0)
        content = dataset.file.read().decode('utf-8')
        self.assertIn("age,name", content)  # Alphabetical order
        self.assertIn("30,John", content)
        self.assertIn("25,Jane", content)
    
    def test_save_converted_csv_handles_single_dict(self):
        """Should handle single dictionary input."""
        from .views import save_converted_csv
        
        json_data = {"name": "John", "age": 30}
        dataset = save_converted_csv("single-dict", json_data)
        
        self.assertEqual(dataset.name, "single-dict")
        self.assertEqual(dataset.source_json, json_data)
    
    def test_save_converted_csv_creates_proper_filename(self):
        """Should create CSV file with proper naming."""
        from .views import save_converted_csv
        
        dataset = save_converted_csv("my-dataset", self.sample_json)
        
        # Check that file name includes the dataset name
        self.assertTrue(dataset.file.name.endswith('.csv'))
        self.assertIn('my-dataset', dataset.file.name)
    
    @patch('save_to_database.views.json_to_csv_bytes')
    def test_save_converted_csv_handles_conversion_error(self, mock_converter):
        """Should handle JSON to CSV conversion errors."""
        from .views import save_converted_csv
        
        mock_converter.side_effect = Exception("Conversion failed")
        
        with self.assertRaises(Exception):
            save_converted_csv("error-test", self.sample_json)
    
    @patch('save_to_database.views.CSV.objects.create')
    def test_save_converted_csv_handles_database_error(self, mock_create):
        """Should handle database creation errors."""
        from .views import save_converted_csv
        
        mock_create.side_effect = Exception("Database error")
        
        with self.assertRaises(Exception):
            save_converted_csv("db-error-test", self.sample_json)


class CreateCsvRecordViewPositiveTests(ViewsTestCase):
    """Test successful scenarios for create_csv_record view."""
    
    def test_create_csv_record_success(self):
        """Should create CSV record successfully with valid data."""
        response = self.client.post(
            reverse('save_to_database:create_csv_record'),
            data=json.dumps(self.valid_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        response_data = response.json()
        
        # Check response structure
        expected_keys = ['id', 'name', 'file_url', 'uploaded_url', 'created_at']
        for key in expected_keys:
            self.assertIn(key, response_data)
        
        # Check response values
        self.assertEqual(response_data['name'], 'test-dataset')
        
        # Verify database record
        csv_record = CSV.objects.get(id=response_data['id'])
        self.assertEqual(csv_record.name, 'test-dataset')
        self.assertEqual(csv_record.source_json, self.sample_json)
    
    def test_create_csv_record_complex_json(self):
        """Should handle complex JSON structures."""
        complex_data = {
            "name": "complex-dataset",
            "source_json": [
                {
                    "id": 1,
                    "name": "John",
                    "details": {"age": 30, "city": "NYC"},
                    "tags": ["admin", "user"]
                }
            ]
        }
        
        response = self.client.post(
            reverse('save_to_database:create_csv_record'),
            data=json.dumps(complex_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        response_data = response.json()
        self.assertEqual(response_data['name'], 'complex-dataset')
    
    def test_create_csv_record_with_special_characters(self):
        """Should handle names with special characters."""
        data = {
            "name": "dataset-with-special_chars@123",
            "source_json": self.sample_json
        }
        
        response = self.client.post(
            reverse('save_to_database:create_csv_record'),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        response_data = response.json()
        self.assertEqual(response_data['name'], 'dataset-with-special_chars@123')


class CreateCsvRecordViewNegativeTests(ViewsTestCase):
    """Test error scenarios for create_csv_record view."""
    
    def test_create_csv_record_wrong_method(self):
        """Should return 405 for non-POST requests."""
        response = self.client.get(reverse('save_to_database:create_csv_record'))
        self.assertEqual(response.status_code, 405)
        
        response_data = response.json()
        self.assertIn('error', response_data)
        self.assertEqual(response_data['error'], 'Only POST method allowed')
    
    def test_create_csv_record_invalid_json(self):
        """Should return 400 for invalid JSON."""
        response = self.client.post(
            reverse('save_to_database:create_csv_record'),
            data="invalid json string",
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertEqual(response_data['error'], 'Invalid JSON')
    
    def test_create_csv_record_missing_name(self):
        """Should return 400 when name is missing."""
        data = {"source_json": self.sample_json}
        
        response = self.client.post(
            reverse('save_to_database:create_csv_record'),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertEqual(response_data['error'], 'Name is required')
    
    def test_create_csv_record_empty_name(self):
        """Should return 400 for empty name string."""
        data = {
            "name": "",
            "source_json": self.sample_json
        }
        
        response = self.client.post(
            reverse('save_to_database:create_csv_record'),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertEqual(response_data['error'], 'Name is required')
    
    def test_create_csv_record_whitespace_name(self):
        """Should return 400 for whitespace-only name."""
        data = {
            "name": "   \t\n  ",
            "source_json": self.sample_json
        }
        
        response = self.client.post(
            reverse('save_to_database:create_csv_record'),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertEqual(response_data['error'], 'Name is required')
    
    def test_create_csv_record_missing_source_json(self):
        """Should return 400 when source_json is missing."""
        data = {"name": "test-dataset"}
        
        response = self.client.post(
            reverse('save_to_database:create_csv_record'),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertEqual(response_data['error'], 'source_json is required')
    
    def test_create_csv_record_none_source_json(self):
        """Should return 400 when source_json is explicitly None."""
        data = {
            "name": "test-dataset",
            "source_json": None
        }
        
        response = self.client.post(
            reverse('save_to_database:create_csv_record'),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertEqual(response_data['error'], 'source_json is required')
    
    @patch('save_to_database.views.save_converted_csv')
    @patch('save_to_database.views.logger')
    def test_create_csv_record_handles_save_error(self, mock_logger, mock_save_csv):
        """Should handle errors from save_converted_csv function."""
        mock_save_csv.side_effect = Exception("Save failed")
        
        response = self.client.post(
            reverse('save_to_database:create_csv_record'),
            data=json.dumps(self.valid_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 500)
        response_data = response.json()
        self.assertEqual(response_data['error'], 'Failed to create CSV record')
        self.assertIn('details', response_data)
        
        # Verify logging
        mock_logger.exception.assert_called_with("Error creating CSV record")
    
    @patch('save_to_database.views.logger')
    def test_create_csv_record_handles_unexpected_error(self, mock_logger):
        """Should handle unexpected errors gracefully."""
        with patch('save_to_database.views.save_converted_csv') as mock_save_csv:
            mock_save_csv.side_effect = KeyError("Unexpected key error")
            
            response = self.client.post(
                reverse('save_to_database:create_csv_record'),
                data=json.dumps(self.valid_data),
                content_type='application/json'
            )
            
            self.assertEqual(response.status_code, 500)
            response_data = response.json()
            self.assertEqual(response_data['error'], 'Failed to create CSV record')
            self.assertIn('details', response_data)
            
            mock_logger.exception.assert_called_with("Error creating CSV record")


class CreateCsvRecordViewEdgeCaseTests(ViewsTestCase):
    """Test edge cases for create_csv_record view."""
    
    def test_create_csv_record_empty_source_json_list(self):
        """Should handle empty list as source_json."""
        data = {
            "name": "empty-dataset",
            "source_json": []
        }
        
        response = self.client.post(
            reverse('save_to_database:create_csv_record'),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        response_data = response.json()
        self.assertEqual(response_data['name'], 'empty-dataset')
    
    def test_create_csv_record_empty_source_json_dict(self):
        """Should handle empty dict as source_json."""
        data = {
            "name": "empty-dict-dataset",
            "source_json": {}
        }
        
        response = self.client.post(
            reverse('save_to_database:create_csv_record'),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        response_data = response.json()
        self.assertEqual(response_data['name'], 'empty-dict-dataset')
    
    def test_create_csv_record_long_name_within_limit(self):
        """Should handle reasonably long dataset names."""
        long_name = "a" * 150  # Within reasonable limits
        data = {
            "name": long_name,
            "source_json": self.sample_json
        }
        
        response = self.client.post(
            reverse('save_to_database:create_csv_record'),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        response_data = response.json()
        self.assertEqual(response_data['name'], long_name)
    
    def test_create_csv_record_unicode_name(self):
        """Should handle Unicode characters in name."""
        data = {
            "name": "test-dataset-français",
            "source_json": self.sample_json
        }
        
        response = self.client.post(
            reverse('save_to_database:create_csv_record'),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        response_data = response.json()
        self.assertEqual(response_data['name'], 'test-dataset-français')


class ResponseFormatTests(ViewsTestCase):
    """Test response format consistency."""
    
    def test_success_response_format(self):
        """Success responses should have consistent format."""
        response = self.client.post(
            reverse('save_to_database:create_csv_record'),
            data=json.dumps(self.valid_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        response_data = response.json()
        
        # Required fields
        required_fields = ['id', 'name', 'file_url', 'uploaded_url', 'created_at']
        for field in required_fields:
            self.assertIn(field, response_data)
        
        # Data types
        self.assertIsInstance(response_data['id'], int)
        self.assertIsInstance(response_data['name'], str)
        self.assertIsInstance(response_data['created_at'], str)
    
    def test_error_response_format(self):
        """Error responses should have consistent format."""
        response = self.client.post(
            reverse('save_to_database:create_csv_record'),
            data="invalid json",
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        
        # Should have error field
        self.assertIn('error', response_data)
        self.assertIsInstance(response_data['error'], str)
    
    def test_server_error_response_format(self):
        """Server error responses should have consistent format."""
        with patch('save_to_database.views.save_converted_csv', side_effect=Exception("Test error")):
            response = self.client.post(
                reverse('save_to_database:create_csv_record'),
                data=json.dumps(self.valid_data),
                content_type='application/json'
            )
        
        self.assertEqual(response.status_code, 500)
        response_data = response.json()
        
        # Should have error and details fields
        self.assertIn('error', response_data)
        self.assertIn('details', response_data)
        self.assertIsInstance(response_data['error'], str)
        self.assertIsInstance(response_data['details'], str)