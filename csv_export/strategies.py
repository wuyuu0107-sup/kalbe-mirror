from abc import ABC, abstractmethod
import csv

class ExportStrategy(ABC):
    """Strategy Pattern: Abstract strategy for data export"""
    
    @abstractmethod
    def export(self, data, writer_or_response):
        pass

class CSVExportStrategy(ExportStrategy):
    """Concrete Strategy: CSV Export Implementation"""
    
    def export(self, data, writer):
        from csv_export.utility.json_to_csv import json_to_csv
        json_to_csv(data, writer)