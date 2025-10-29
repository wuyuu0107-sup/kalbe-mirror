from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class StorageProvider(ABC):
    """Abstract interface for storage providers"""
    
    @abstractmethod
    def list_files(self, bucket_name: str) -> List[Dict[str, Any]]:
        """List all files in a bucket"""
        pass

class SearchStrategy(ABC):
    """Abstract interface for different search strategies"""
    
    @abstractmethod
    def search(self, files: List[Dict[str, Any]], search_term: str, extension: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search files using specific strategy"""
        pass