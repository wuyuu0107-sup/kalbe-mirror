from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class StorageProvider(ABC):
    """Interface for storage providers"""
    @abstractmethod
    def list_files(self, bucket_name: str) -> List[Dict[str, Any]]:
        """List all files in a bucket"""
        pass

    @abstractmethod
    def get_file(self, bucket_name: str, file_path: str) -> Optional[bytes]:
        """Get file content"""
        pass

    @abstractmethod
    def delete_file(self, bucket_name: str, file_path: str) -> bool:
        """Delete a file"""
        pass

class SearchStrategy(ABC):
    """Abstract interface for different search strategies"""
    
    @abstractmethod
    def search(self, files: List[Dict[str, Any]], search_term: str, extension: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search files using specific strategy"""
        pass

    def test_abstract_interfaces(self):
        """Test abstract interfaces raise NotImplementedError"""
        from .interfaces import StorageProvider, SearchStrategy
        
        class TestStorageProvider(StorageProvider):
            pass
            
        class TestSearchStrategy(SearchStrategy):
            pass
        
        with self.assertRaises(TypeError):
            TestStorageProvider()
            
        with self.assertRaises(TypeError):
            TestSearchStrategy()