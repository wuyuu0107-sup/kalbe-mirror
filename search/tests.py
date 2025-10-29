# search/tests.py
from unittest.mock import patch, MagicMock
from django.test import TestCase
from .services import search_storage_files

class StorageSearchTests(TestCase):
    """Test suite for Supabase storage search functionality"""

    def setUp(self):
        """Set up test environment with mocked Supabase client"""
        self.mock_supabase_patcher = patch('search.services.create_client')
        self.mock_create_client = self.mock_supabase_patcher.start()
        self.mock_client = MagicMock()
        self.mock_create_client.return_value = self.mock_client
        self.mock_storage = MagicMock()
        self.mock_client.storage = self.mock_storage
        self.mock_bucket = MagicMock()
        self.mock_storage.from_.return_value = self.mock_bucket

    def tearDown(self):
        """Clean up mocks after tests"""
        self.mock_supabase_patcher.stop()

    def test_search_files_exact_match(self):
        """Test searching files with exact name match"""
        # Mock the list method to return some test files
        self.mock_bucket.list.return_value = [
            {'name': 'test.csv', 'id': '1'},
            {'name': 'sample.csv', 'id': '2'},
            {'name': 'test2.csv', 'id': '3'}
        ]

        # Search for files with 'test' in the name
        results = search_storage_files(bucket_name="test-bucket", search_term="test")

        # Assert the bucket was queried
        self.mock_storage.from_.assert_called_once_with("test-bucket")
        self.mock_bucket.list.assert_called_once()

        # Verify correct files were returned
        self.assertEqual(len(results), 2)
        self.assertTrue(any(f['name'] == 'test.csv' for f in results))
        self.assertTrue(any(f['name'] == 'test2.csv' for f in results))

    def test_search_files_case_insensitive(self):
        """Test that search is case insensitive"""
        self.mock_bucket.list.return_value = [
            {'name': 'TEST.csv', 'id': '1'},
            {'name': 'test.csv', 'id': '2'},
            {'name': 'Sample.csv', 'id': '3'}
        ]

        results = search_storage_files(bucket_name="test-bucket", search_term="test")

        self.assertEqual(len(results), 2)
        self.assertTrue(any(f['name'].lower() == 'test.csv' for f in results))
        self.assertTrue(any(f['name'] == 'TEST.csv' for f in results))

    def test_search_files_no_matches(self):
        """Test behavior when no files match search term"""
        self.mock_bucket.list.return_value = [
            {'name': 'sample1.csv', 'id': '1'},
            {'name': 'sample2.csv', 'id': '2'}
        ]

        results = search_storage_files(bucket_name="test-bucket", search_term="test")

        self.assertEqual(len(results), 0)

    def test_search_files_empty_bucket(self):
        """Test searching in an empty bucket"""
        self.mock_bucket.list.return_value = []

        results = search_storage_files(bucket_name="test-bucket", search_term="test")

        self.assertEqual(len(results), 0)

    def test_search_files_connection_error(self):
        """Test handling of connection errors"""
        self.mock_bucket.list.side_effect = Exception("Connection error")

        with self.assertRaises(Exception):
            search_storage_files(bucket_name="test-bucket", search_term="test")

    def test_search_files_with_extension_filter(self):
        """Test searching files with specific extension filter"""
        self.mock_bucket.list.return_value = [
            {'name': 'test.csv', 'id': '1'},
            {'name': 'test.pdf', 'id': '2'},
            {'name': 'sample.csv', 'id': '3'}
        ]

        results = search_storage_files(
            bucket_name="test-bucket", 
            search_term="test",
            extension=".csv"
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'test.csv')