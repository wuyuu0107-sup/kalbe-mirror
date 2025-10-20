import os
import json
from unittest.mock import patch, MagicMock
from django.http import JsonResponse
from django.test import TestCase
from save_to_database.utility.json_to_csv_bytes import json_to_csv_bytes
from save_to_database.utility.upload_csv_to_supabase import upload_csv_to_supabase
from save_to_database.utility.validate_payload import validate_payload


class JsonToCsvBytesPositiveTests(TestCase):
    """Test successful JSON to CSV conversion scenarios."""
    
    def test_convert_list_of_dicts(self):
        """Should convert list of dictionaries to CSV bytes."""
        data = [
            {"name": "John", "age": 30},
            {"name": "Jane", "age": 25}
        ]
        result = json_to_csv_bytes(data)
        
        self.assertIsInstance(result, bytes)
        csv_string = result.decode('utf-8')
        # CSV writer sorts field names alphabetically
        self.assertIn("age,name", csv_string)
        self.assertIn("30,John", csv_string)
        self.assertIn("25,Jane", csv_string)

    def test_convert_single_dict(self):
        """Should convert single dictionary to CSV bytes."""
        data = {"name": "John", "age": 30}
        result = json_to_csv_bytes(data)
        
        csv_string = result.decode('utf-8')
        self.assertIn("age,name", csv_string)  # sorted fieldnames
        self.assertIn("30,John", csv_string)

    def test_convert_nested_objects(self):
        """Should flatten nested objects using flatten_json."""
        data = [{
            "name": "John",
            "contact": {
                "email": "john@example.com",
                "phone": "+1-555-0123"
            }
        }]
        
        with patch('save_to_database.utility.json_to_csv_bytes.flatten_json') as mock_flatten:
            mock_flatten.return_value = {
                "name": "John",
                "contact.email": "john@example.com",
                "contact.phone": "+1-555-0123"
            }
            
            result = json_to_csv_bytes(data)
            mock_flatten.assert_called_once()
            
            csv_string = result.decode('utf-8')
            self.assertIn("contact.email", csv_string)

    def test_handles_none_values(self):
        """Should handle None values correctly."""
        data = [{"name": "John", "age": None}]
        result = json_to_csv_bytes(data)
        
        csv_string = result.decode('utf-8')
        # None becomes empty string, check the order (age,name)
        self.assertIn(",John", csv_string)  # empty age field

    def test_handles_complex_nested_values(self):
        """Should handle complex nested values as JSON strings."""
        data = [{
            "name": "John",
            "settings": {"theme": "dark", "notifications": True},
            "tags": ["admin", "user"]
        }]
        
        with patch('save_to_database.utility.json_to_csv_bytes.flatten_json') as mock_flatten:
            mock_flatten.return_value = {
                "name": "John",
                "settings": {"theme": "dark", "notifications": True},
                "tags": ["admin", "user"]
            }
            
            result = json_to_csv_bytes(data)
            csv_string = result.decode('utf-8')
            # Check for JSON content (CSV escapes quotes)
            self.assertIn('dark', csv_string)


class JsonToCsvBytesNegativeTests(TestCase):
    """Test edge cases and error handling for JSON to CSV conversion."""
    
    def test_convert_empty_list(self):
        """Should return empty bytes for empty list."""
        result = json_to_csv_bytes([])
        self.assertEqual(result, b"")

    def test_convert_empty_dict(self):
        """Should handle empty dict gracefully."""
        result = json_to_csv_bytes({})
        # Empty dict creates CSV with no headers, just line endings
        self.assertIn(result, [b"", b"\r\n\r\n"])  # Accept both possibilities

    def test_convert_none_input(self):
        """Should handle None input gracefully."""
        result = json_to_csv_bytes(None)
        self.assertEqual(result, b"")

    def test_handles_mixed_field_types(self):
        """Should handle records with different field sets."""
        data = [
            {"name": "John", "age": 30},
            {"name": "Jane", "city": "NYC"}  # Different fields
        ]
        result = json_to_csv_bytes(data)
        
        csv_string = result.decode('utf-8')
        # Should include all fields from all records
        self.assertIn("age", csv_string)
        self.assertIn("city", csv_string)
        self.assertIn("name", csv_string)


class UploadCsvToSupabasePositiveTests(TestCase):
    """Test successful Supabase upload scenarios."""
    
    def test_upload_disabled_returns_none(self):
        """Should return None when SUPABASE_UPLOAD_ENABLED is false."""
        with patch.dict(os.environ, {'SUPABASE_UPLOAD_ENABLED': 'false'}):
            result = upload_csv_to_supabase(b"test", "bucket", "path")
            self.assertIsNone(result)

    @patch.dict(os.environ, {
        'SUPABASE_UPLOAD_ENABLED': 'true',
        'SUPABASE_URL': 'https://test.supabase.co',
        'SUPABASE_SERVICE_ROLE_KEY': 'test-key'
    })
    def test_successful_upload(self):
        """Should successfully upload and return public URL."""
        # Mock the entire supabase module
        with patch('builtins.__import__') as mock_import:
            mock_supabase = MagicMock()
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            
            # Set up the import mock
            def side_effect(name, *args, **kwargs):
                if name == 'supabase':
                    return mock_supabase
                # For other imports, use the real import
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = side_effect
            mock_supabase.create_client.return_value = mock_client
            mock_client.storage.from_.return_value = mock_bucket
            mock_bucket.get_public_url.return_value = "https://example.com/test.csv"
            
            result = upload_csv_to_supabase(b"test,data", "test-bucket", "test.csv")
            
            mock_bucket.upload.assert_called()
            mock_bucket.get_public_url.assert_called_with("test.csv")
            self.assertEqual(result, "https://example.com/test.csv")

    @patch.dict(os.environ, {
        'SUPABASE_UPLOAD_ENABLED': 'true',
        'SUPABASE_URL': 'https://test.supabase.co',
        'SUPABASE_SERVICE_ROLE_KEY': 'test-key'
    })
    def test_public_url_dict_response_with_public_url_key(self):
        """Should handle dict response with 'public_url' key."""
        with patch('builtins.__import__') as mock_import:
            mock_supabase = MagicMock()
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            
            def side_effect(name, *args, **kwargs):
                if name == 'supabase':
                    return mock_supabase
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = side_effect
            mock_supabase.create_client.return_value = mock_client
            mock_client.storage.from_.return_value = mock_bucket
            mock_bucket.get_public_url.return_value = {"public_url": "https://example.com/test.csv"}
            
            result = upload_csv_to_supabase(b"test", "bucket", "test.csv")
            self.assertEqual(result, "https://example.com/test.csv")

    @patch.dict(os.environ, {
        'SUPABASE_UPLOAD_ENABLED': 'true',
        'SUPABASE_URL': 'https://test.supabase.co',
        'SUPABASE_SERVICE_ROLE_KEY': 'test-key'
    })
    def test_public_url_dict_response_with_publicurl_key(self):
        """Should handle dict response with 'publicURL' key."""
        with patch('builtins.__import__') as mock_import:
            mock_supabase = MagicMock()
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            
            def side_effect(name, *args, **kwargs):
                if name == 'supabase':
                    return mock_supabase
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = side_effect
            mock_supabase.create_client.return_value = mock_client
            mock_client.storage.from_.return_value = mock_bucket
            mock_bucket.get_public_url.return_value = {"publicURL": "https://example.com/test.csv"}
            
            result = upload_csv_to_supabase(b"test", "bucket", "test.csv")
            self.assertEqual(result, "https://example.com/test.csv")


class UploadCsvToSupabaseNegativeTests(TestCase):
    """Test error handling and edge cases for Supabase upload."""
    
    def test_missing_credentials(self):
        """Should return None when Supabase credentials are missing."""
        with patch.dict(os.environ, {
            'SUPABASE_UPLOAD_ENABLED': 'true',
            'SUPABASE_URL': '',
            'SUPABASE_SERVICE_ROLE_KEY': ''
        }):
            with patch('save_to_database.utility.upload_csv_to_supabase.logger') as mock_logger:
                result = upload_csv_to_supabase(b"test", "bucket", "path")
                self.assertIsNone(result)
                mock_logger.warning.assert_called()

    def test_missing_supabase_package(self):
        """Should handle missing supabase package gracefully."""
        with patch.dict(os.environ, {
            'SUPABASE_UPLOAD_ENABLED': 'true',
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_SERVICE_ROLE_KEY': 'test-key'
        }):
            with patch('builtins.__import__', side_effect=ImportError("No module named supabase")):
                with patch('save_to_database.utility.upload_csv_to_supabase.logger') as mock_logger:
                    result = upload_csv_to_supabase(b"test", "bucket", "path")
                    self.assertIsNone(result)
                    mock_logger.exception.assert_called()

    def test_upload_disabled_env_variants(self):
        """Should handle different ways of disabling upload."""
        test_cases = ['false', 'False', 'FALSE', '0', 'no', 'off', '']
        
        for value in test_cases:
            with self.subTest(env_value=value):
                with patch.dict(os.environ, {'SUPABASE_UPLOAD_ENABLED': value}):
                    result = upload_csv_to_supabase(b"test", "bucket", "path")
                    self.assertIsNone(result)

class TestLine50Coverage(TestCase):
    """Test to cover line 50 - fallback return path"""
    
    @patch.dict(os.environ, {
        'SUPABASE_UPLOAD_ENABLED': 'true',
        'SUPABASE_URL': 'https://test.supabase.co',
        'SUPABASE_SERVICE_ROLE_KEY': 'test-key'
    })
    def test_fallback_return_path(self):
        """Test line 50 - should return path when public URL is neither dict nor string"""
        with patch('builtins.__import__') as mock_import:
            mock_supabase = MagicMock()
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            
            def side_effect(name, *args, **kwargs):
                if name == 'supabase':
                    return mock_supabase
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = side_effect
            mock_supabase.create_client.return_value = mock_client
            mock_client.storage.from_.return_value = mock_bucket
            
            # Upload succeeds
            mock_bucket.upload.return_value = None
            
            # get_public_url returns something that's neither dict nor string (like None, int, list, etc.)
            mock_bucket.get_public_url.return_value = None  # This triggers line 50
            
            result = upload_csv_to_supabase(b"test,data", "bucket", "test/path.csv")
            
            # Should return the path as fallback
            self.assertEqual(result, "test/path.csv")

class ValidatePayloadTests(TestCase):

    def test_valid_payload_dict(self):
        """Valid JSON dict should return payload dict and no error."""
        raw_body = json.dumps({"name": "dataset1", "source_json": [{"a": 1}]})
        payload, error = validate_payload(raw_body)
        self.assertIsNone(error)
        self.assertEqual(payload['name'], "dataset1")
        self.assertEqual(payload['source_json'], [{"a": 1}])

    def test_valid_payload_list(self):
        """Valid JSON list for source_json should work."""
        raw_body = json.dumps({"name": "dataset2", "source_json": []})
        payload, error = validate_payload(raw_body)
        self.assertIsNone(error)
        self.assertEqual(payload['name'], "dataset2")
        self.assertEqual(payload['source_json'], [])

    def test_missing_name(self):
        """Missing 'name' should return JsonResponse error."""
        raw_body = json.dumps({"source_json": [{"a": 1}]})
        payload, error = validate_payload(raw_body)
        self.assertIsInstance(error, JsonResponse)
        self.assertIsNone(payload)
        self.assertEqual(error.status_code, 400)

    def test_empty_name(self):
        """Empty string name should return JsonResponse error."""
        raw_body = json.dumps({"name": "  ", "source_json": [{"a": 1}]})
        payload, error = validate_payload(raw_body)
        self.assertIsInstance(error, JsonResponse)
        self.assertIsNone(payload)
        self.assertEqual(error.status_code, 400)

    def test_missing_source_json(self):
        """Missing source_json should return JsonResponse error."""
        raw_body = json.dumps({"name": "dataset3"})
        payload, error = validate_payload(raw_body)
        self.assertIsInstance(error, JsonResponse)
        self.assertIsNone(payload)
        self.assertEqual(error.status_code, 400)

    def test_invalid_json(self):
        """Malformed JSON should return JsonResponse error."""
        raw_body = "this is not json"
        payload, error = validate_payload(raw_body)
        self.assertIsInstance(error, JsonResponse)
        self.assertIsNone(payload)
        self.assertEqual(error.status_code, 400)

class UploadCsvToSupabaseExceptionFallbackTests(TestCase):
    """Covers nested exception handling in upload_csv_to_supabase (lines 37–42)."""

    @patch.dict(os.environ, {
        'SUPABASE_UPLOAD_ENABLED': 'true',
        'SUPABASE_URL': 'https://test.supabase.co',
        'SUPABASE_SERVICE_ROLE_KEY': 'test-key'
    })
    def test_double_upload_failure_triggers_logger_and_returns_none(self):
        """Should log and return None when both upload attempts fail."""
        with patch('builtins.__import__') as mock_import, \
             patch('save_to_database.utility.upload_csv_to_supabase.logger') as mock_logger:
            
            mock_supabase = MagicMock()
            mock_client = MagicMock()
            mock_bucket = MagicMock()
            
            # Make both upload attempts raise exceptions
            mock_bucket.upload.side_effect = [Exception("first fail"), Exception("second fail")]
            
            # Set up Supabase client mock
            def side_effect(name, *args, **kwargs):
                if name == 'supabase':
                    return mock_supabase
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = side_effect
            mock_supabase.create_client.return_value = mock_client
            mock_client.storage.from_.return_value = mock_bucket
            
            # Run function
            result = upload_csv_to_supabase(b"data", "bucket", "path.csv")
            
            # Assertions
            self.assertIsNone(result)
            self.assertEqual(mock_bucket.upload.call_count, 2)  # both attempts tried
            mock_logger.exception.assert_called_with("Supabase upload failed")
