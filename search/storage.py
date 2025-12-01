
from typing import List, Dict, Any, Optional
from .interfaces import StorageProvider
from save_to_database.models import CSV
import os
import requests

class DatabaseCSVStorageProvider(StorageProvider):
    """Storage provider that lists CSVs from the database."""

    def list_files(self, bucket_name: str) -> List[Dict[str, Any]]:
        """
        List all CSV files in the database. Ignores bucket_name (for compatibility).
        Returns a list of dicts with at least 'name' and 'id'.
        """
        files = CSV.objects.all()
        return [
            {
                'name': os.path.basename(csv.file.name) if csv.file else None,
                'id': csv.id,
                'file_path': csv.file.name,
                'created_at': csv.created_at,
                'record_count': csv.record_count,
            }
            for csv in files
        ]

    def get_file(self, bucket_name: str, file_path: str) -> Optional[bytes]:
        """
        Get file content from the Supabase public URL (uploaded_url).
        """
        try:
            csv = CSV.objects.filter(file=file_path).first()
            if csv and csv.uploaded_url:
                response = requests.get(csv.uploaded_url)
                response.raise_for_status()
                return response.content
            return None
        except Exception as e:
            raise Exception(f"Error reading CSV file from Supabase URL: {str(e)}")

    def delete_file(self, bucket_name: str, file_path: str) -> bool:
        """
        Delete a CSV file from the database and storage.
        """
        try:
            csv = CSV.objects.filter(file=file_path).first()
            if csv:
                csv.delete()
                return True
            return False
        except Exception as e:
            raise Exception(f"Error deleting CSV file: {str(e)}")