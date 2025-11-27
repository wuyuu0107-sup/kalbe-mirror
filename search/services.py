from typing import List, Dict, Any, Optional
from .interfaces import StorageProvider, SearchStrategy
from .storage import SupabaseStorageProvider
from .strategies import NameBasedSearchStrategy

class SearchService:
    """Service class that coordinates storage and search operations"""
    
    def __init__(self, storage_provider: StorageProvider = None, search_strategy: SearchStrategy = None):
        """Initialize with optional storage provider and search strategy"""
        self.storage_provider = storage_provider or SupabaseStorageProvider()
        self.search_strategy = search_strategy or NameBasedSearchStrategy()

    def search_files(self, bucket_name: str, search_term: str, extension: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search files in storage using configured strategy"""
        # Get files from storage
        files = self.storage_provider.list_files(bucket_name)
        
        # Apply search strategy
        return self.search_strategy.search(files, search_term, extension)

def search_storage_files(
    bucket_name: str,
    search_term: str,
    extension: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Convenience function for backwards compatibility with tests.

    Guarantees:
    - Never returns None
    - Never returns a non-list
    - Never returns a list containing non-dict items
    """

    search_service = SearchService()
    result = search_service.search_files(bucket_name, search_term, extension)

    # Normalize None → []
    if result is None:
        return []

    # Normalize non-list → []
    if not isinstance(result, list):
        return []

    # Normalize lists containing invalid items
    safe_list: List[Dict[str, Any]] = []
    for item in result:
        if isinstance(item, dict):
            safe_list.append(item)

    return safe_list

