from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class SearchCriteria:
    query: str
    filters: Optional[dict] = None

@dataclass
class SearchResult:
    id: int
    title: str
    content: str
    relevance_score: float

class SearchCommand(ABC):
    @abstractmethod
    def execute(self) -> List[SearchResult]:
        pass

    @abstractmethod
    def undo(self) -> None:
        pass

class SimpleSearchCommand(SearchCommand):
    def __init__(self, criteria: SearchCriteria, search_service):
        self.criteria = criteria
        self.search_service = search_service
        self.last_results = None

    def execute(self) -> List[SearchResult]:
        self.last_results = self.search_service.search(self.criteria.query)
        return self.last_results

    def undo(self) -> None:
        self.last_results = None

class FilteredSearchCommand(SearchCommand):
    def __init__(self, criteria: SearchCriteria, search_service):
        self.criteria = criteria
        self.search_service = search_service
        self.last_results = None

    def execute(self) -> List[SearchResult]:
        results = self.search_service.search(self.criteria.query)
        if self.criteria.filters:
            results = self._apply_filters(results)
        self.last_results = results
        return results

    def undo(self) -> None:
        self.last_results = None

    def _apply_filters(self, results: List[SearchResult]) -> List[SearchResult]:
        filtered_results = results
        for key, value in self.criteria.filters.items():
            filtered_results = [r for r in filtered_results 
                              if getattr(r, key, None) == value]
        return filtered_results