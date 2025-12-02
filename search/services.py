from typing import List, Dict, Any, Optional
from .interfaces import StorageProvider, SearchStrategy
from .storage import DatabaseCSVStorageProvider
from .strategies import NameBasedSearchStrategy

class SearchService:
    """Service class that coordinates storage and search operations"""
    
    def __init__(self, storage_provider: StorageProvider = None, search_strategy: SearchStrategy = None):
        """Initialize with optional storage provider and search strategy"""
        self.storage_provider = storage_provider or DatabaseCSVStorageProvider()
        self.search_strategy = search_strategy or NameBasedSearchStrategy()

    def search_files(self, bucket_name: str, search_term: str, extension: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search files in storage using configured strategy"""
        # Get files from storage
        files = self.storage_provider.list_files(bucket_name)
        
        # Apply search strategy
        return self.search_strategy.search(files, search_term, extension)

def search_storage_files(bucket_name: str, search_term: str, extension: Optional[str] = None) -> List[Dict[str, Any]]:
    """Convenience function for backwards compatibility with tests"""
    search_service = SearchService()
    return search_service.search_files(bucket_name, search_term, extension)
