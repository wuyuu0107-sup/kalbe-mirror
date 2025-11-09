from typing import List, Dict, Any, Optional
from .interfaces import SearchStrategy

class NameBasedSearchStrategy(SearchStrategy):
    """Concrete implementation of SearchStrategy using filename-based search"""

    def search(self, files: List[Dict[str, Any]], search_term: str, extension: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search files by name, optionally filtering by extension"""
        results = []
        search_term = search_term.lower()
        
        for file in files:
            filename = file['name'].lower()
            
            # Check if filename contains search term
            if search_term in filename:
                # If extension is specified, check file extension
                if extension:
                    if filename.endswith(extension.lower()):
                        results.append(file)
                else:
                    results.append(file)
                    
        return results