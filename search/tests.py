from unittest.mock import patch, MagicMock, Mock
from django.test import Client, TestCase
import unittest
from typing import Optional

from .services import SearchService, search_storage_files
from .interfaces import SearchStrategy, StorageProvider
from .storage import SupabaseStorageProvider
# TODO: Uncomment when these modules are created
# from .commands import SearchCriteria, SimpleSearchCommand, FilteredSearchCommand
# from .invoker import SearchCommandInvoker
# from .models import SearchResult


class MockStorageProvider(StorageProvider):
    """Mock storage provider for testing"""
    def __init__(self, files=None):
        self.files = files or []
    
    def list_files(self, bucket_name: str):
        return self.files
        
    def get_file(self, bucket_name: str, file_path: str) -> Optional[bytes]:
        """Mock get file implementation"""
        for file in self.files:
            if file['name'] == file_path:
                return b"test content"
        return None
        
    def delete_file(self, bucket_name: str, file_path: str) -> bool:
        """Mock delete file implementation"""
        initial_length = len(self.files)
        self.files = [f for f in self.files if f['name'] != file_path]
        return len(self.files) < initial_length


class StorageSearchTests(TestCase):
    """Test suite for storage search functionality"""

    def test_service_default_providers(self):
        """Test service creates default providers"""
        with patch.dict('os.environ', {
            'SUPABASE_URL': 'http://test.com',
            'SUPABASE_SERVICE_ROLE_KEY': 'test-key'
        }):
            service = SearchService()
            self.assertIsNotNone(service.storage_provider)
            self.assertIsNotNone(service.search_strategy)

    def test_search_service_with_custom_providers(self):
        """Test service with custom providers"""
        storage = MockStorageProvider()
        strategy = MagicMock()
        service = SearchService(storage_provider=storage, search_strategy=strategy)
        
        service.search_files("test", "query")
        
        strategy.search.assert_called_once()

    def test_search_files_connection_error(self):
        """Test handling of connection errors"""
        class FailingStorageProvider(StorageProvider):
            def list_files(self, bucket_name: str):
                raise Exception("Connection error")
                
            def get_file(self, bucket_name: str, file_path: str) -> Optional[bytes]:
                raise Exception("Connection error")
                
            def delete_file(self, bucket_name: str, file_path: str) -> bool:
                raise Exception("Connection error")

        storage = FailingStorageProvider()
        service = SearchService(storage_provider=storage)

        with self.assertRaises(Exception) as ctx:
            service.search_files("test-bucket", "test")
        self.assertIn("Connection error", str(ctx.exception))

    def test_search_files_exact_match(self):
        """Test searching files with exact name match"""
        mock_files = [
            {'name': 'test.csv', 'id': '1'},
            {'name': 'sample.csv', 'id': '2'},
            {'name': 'test2.csv', 'id': '3'}
        ]
        storage = MockStorageProvider(mock_files)
        service = SearchService(storage_provider=storage)

        results = service.search_files("test-bucket", "test")

        self.assertEqual(len(results), 2)
        self.assertTrue(any(f['name'] == 'test.csv' for f in results))
        self.assertTrue(any(f['name'] == 'test2.csv' for f in results))

    def test_search_files_case_insensitive(self):
        """Test that search is case insensitive"""
        mock_files = [
            {'name': 'TEST.csv', 'id': '1'},
            {'name': 'test.csv', 'id': '2'},
            {'name': 'Sample.csv', 'id': '3'}
        ]
        storage = MockStorageProvider(mock_files)
        service = SearchService(storage_provider=storage)

        results = service.search_files("test-bucket", "test")

        self.assertEqual(len(results), 2)
        self.assertTrue(any(f['name'].lower() == 'test.csv' for f in results))
        self.assertTrue(any(f['name'] == 'TEST.csv' for f in results))

    def test_search_files_no_matches(self):
        """Test behavior when no files match search term"""
        mock_files = [
            {'name': 'sample1.csv', 'id': '1'},
            {'name': 'sample2.csv', 'id': '2'}
        ]
        storage = MockStorageProvider(mock_files)
        service = SearchService(storage_provider=storage)

        results = service.search_files("test-bucket", "test")

        self.assertEqual(len(results), 0)

    def test_search_files_empty_bucket(self):
        """Test searching in an empty bucket"""
        storage = MockStorageProvider([])
        service = SearchService(storage_provider=storage)

        results = service.search_files("test-bucket", "test")

        self.assertEqual(len(results), 0)

    def test_search_files_with_extension_filter(self):
        """Test searching files with specific extension filter"""
        mock_files = [
            {'name': 'test.csv', 'id': '1'},
            {'name': 'test.pdf', 'id': '2'},
            {'name': 'sample.csv', 'id': '3'}
        ]
        storage = MockStorageProvider(mock_files)
        service = SearchService(storage_provider=storage)

        results = service.search_files(
            bucket_name="test-bucket", 
            search_term="test",
            extension=".csv"
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'test.csv')

    def test_convenience_function(self):
        """Test the convenience function works same as service"""
        with patch.dict('os.environ', {
            'SUPABASE_URL': 'http://test.com',
            'SUPABASE_SERVICE_ROLE_KEY': 'test-key'
        }):
            # Mock the Supabase client
            mock_files = [{'name': 'test.csv', 'id': '1'}]
            storage = MockStorageProvider(mock_files)
            
            with patch('search.services.SupabaseStorageProvider') as mock_provider:
                mock_provider.return_value = storage
                results = search_storage_files("test-bucket", "test")
                self.assertEqual(len(results), 1)


class ViewTests(TestCase):
    """Test suite for views"""
    
    def setUp(self):
        self.client = Client()
        
    def test_search_files_view(self):
        """Test search files view"""
        with patch('search.views.search_storage_files') as mock_search:
            mock_search.return_value = [{'name': 'test.csv'}]
            
            response = self.client.get('/search/files/', {
                'bucket': 'test-bucket',
                'q': 'test'
            })
            
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()['files']), 1)
    
    def test_search_files_view_missing_params(self):
        """Test search files view with missing parameters"""
        response = self.client.get('/search/files/')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Missing required parameters')
    
    def test_search_files_view_error(self):
        """Test search files view error handling"""
        with patch('search.views.search_storage_files') as mock_search:
            mock_search.side_effect = Exception("Search error")
            
            response = self.client.get('/search/files/', {
                'bucket': 'test-bucket',
                'q': 'test'
            })
            
            self.assertEqual(response.status_code, 500)
            self.assertIn('error', response.json())


class StorageProviderTests(TestCase):
    """Test suite for storage provider"""
    
    def setUp(self):
        self.env_patcher = patch.dict('os.environ', {
            'SUPABASE_URL': 'http://test.com',
            'SUPABASE_SERVICE_ROLE_KEY': 'test-key'
        })
        self.env_patcher.start()
        
        # Create mock response
        self.mock_response = MagicMock()
        self.mock_response.status_code = 200
        self.mock_response.content = b"test content"
        
        # Setup client patcher
        self.client_patcher = patch('supabase.create_client')
        self.mock_create = self.client_patcher.start()
        
        # Setup mock client and storage
        self.mock_client = MagicMock()
        self.mock_storage = MagicMock()
        self.mock_bucket = MagicMock()
        
        self.mock_create.return_value = self.mock_client
        self.mock_client.storage = self.mock_storage
        self.mock_storage.from_.return_value = self.mock_bucket
        
    def tearDown(self):
        self.env_patcher.stop()
        self.client_patcher.stop()

    def test_storage_provider_errors(self):
        """Test error handling in storage provider"""
        self.mock_bucket.download.side_effect = Exception("Download error")
        self.mock_bucket.remove.side_effect = Exception("Delete error")
        self.mock_bucket.list.side_effect = Exception("List error")
        
        provider = SupabaseStorageProvider()
        
        with self.assertRaises(Exception) as ctx:
            provider.get_file("test-bucket", "test.csv")
        self.assertIn("Error downloading file", str(ctx.exception))
        
        with self.assertRaises(Exception) as ctx:
            provider.delete_file("test-bucket", "test.csv")
        self.assertIn("Error deleting file", str(ctx.exception))
        
        with self.assertRaises(Exception) as ctx:
            provider.list_files("test-bucket")
        self.assertIn("Error listing files", str(ctx.exception))


class SearchStrategyTests(TestCase):
    """Test suite for search strategies"""
    
    def test_name_based_search(self):
        """Test name based search strategy"""
        from .strategies import NameBasedSearchStrategy
        
        strategy = NameBasedSearchStrategy()
        files = [
            {'name': 'test.csv'},
            {'name': 'test.pdf'},
            {'name': 'other.csv'}
        ]
        
        # Test without extension filter
        results = strategy.search(files, "test")
        self.assertEqual(len(results), 2)
        
        # Test with extension filter
        results = strategy.search(files, "test", extension=".pdf")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'test.pdf')
        
        # Test case insensitive
        results = strategy.search(files, "TEST")
        self.assertEqual(len(results), 2)
        
        # Test no matches
        results = strategy.search(files, "nonexistent")
        self.assertEqual(len(results), 0)


class InterfaceTests(TestCase):
    """Test suite for interfaces"""
    
    def test_storage_provider_interface(self):
        """Test StorageProvider interface"""
        with self.assertRaises(TypeError):
            StorageProvider()
            
        class PartialProvider(StorageProvider):
            def list_files(self, bucket_name: str):
                pass
                
        with self.assertRaises(TypeError):
            PartialProvider()
            
    def test_search_strategy_interface(self):
        """Test SearchStrategy interface"""
        with self.assertRaises(TypeError):
            SearchStrategy()
            
        class PartialStrategy(SearchStrategy):
            pass
            
        with self.assertRaises(TypeError):
            PartialStrategy()


# TODO: Uncomment this class when commands.py, invoker.py, and SearchResult are created
"""
class TestSearchCommands(unittest.TestCase):
    Test suite for search commands
    
    def setUp(self):
        self.mock_service = Mock()
        self.invoker = SearchCommandInvoker()
        self.sample_results = [
            SearchResult(id=1, title="Test1", content="Content1", relevance_score=0.9),
            SearchResult(id=2, title="Test2", content="Content2", relevance_score=0.8)
        ]
        self.mock_service.search.return_value = self.sample_results

    def test_simple_search_command(self):
        Test simple search command execution
        # Arrange
        criteria = SearchCriteria(query="test")
        command = SimpleSearchCommand(criteria, self.mock_service)

        # Act
        results = self.invoker.execute_command(command)

        # Assert
        self.assertEqual(len(results), 2)
        self.mock_service.search.assert_called_once_with("test")

    def test_filtered_search_command(self):
        Test filtered search command execution
        # Arrange
        criteria = SearchCriteria(
            query="test",
            filters={"relevance_score": 0.9}
        )
        command = FilteredSearchCommand(criteria, self.mock_service)

        # Act
        results = self.invoker.execute_command(command)

        # Assert
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].relevance_score, 0.9)

    def test_command_undo(self):
        Test command undo functionality
        # Arrange
        criteria = SearchCriteria(query="test")
        command = SimpleSearchCommand(criteria, self.mock_service)

        # Act
        self.invoker.execute_command(command)
        self.invoker.undo_last()

        # Assert
        self.assertIsNone(command.last_results)

    def test_command_history(self):
        Test command history tracking
        # Arrange
        criteria1 = SearchCriteria(query="test1")
        criteria2 = SearchCriteria(query="test2")
        command1 = SimpleSearchCommand(criteria1, self.mock_service)
        command2 = SimpleSearchCommand(criteria2, self.mock_service)

        # Act
        self.invoker.execute_command(command1)
        self.invoker.execute_command(command2)

        # Assert
        self.assertEqual(len(self.invoker._history), 2)
"""