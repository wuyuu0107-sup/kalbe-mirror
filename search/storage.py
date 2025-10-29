from typing import List, Dict, Any, Optional
from .interfaces import StorageProvider
from supabase import create_client
import os

class SupabaseStorageProvider(StorageProvider):
    """Concrete implementation of StorageProvider for Supabase"""

    def __init__(self):
        self.supabase = create_client(
            os.getenv('SUPABASE_URL', ''),
            os.getenv('SUPABASE_KEY', '')
        )

    def list_files(self, bucket_name: str) -> List[Dict[str, Any]]:
        """List all files from Supabase storage bucket"""
        try:
            storage = self.supabase.storage
            bucket = storage.from_(bucket_name)
            return bucket.list()
        except Exception as e:
            raise Exception(f"Storage error: {str(e)}")