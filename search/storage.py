import os
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from .interfaces import StorageProvider

class SupabaseStorageError(RuntimeError):
    """Wraps errors coming from Supabase storage operations."""
    pass

class SupabaseStorageProvider(StorageProvider):
    """Supabase implementation of storage provider"""
    
    def __init__(self):
        """Initialize Supabase client"""
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        if not url or not key:
            raise ValueError("Supabase configuration missing")
        self.client = create_client(url, key)

    def list_files(self, bucket_name: str) -> List[Dict[str, Any]]:
        """List all files in a Supabase storage bucket"""
        try:
            bucket = self.client.storage.from_(bucket_name)
            return bucket.list()
        except Exception as e:
            raise SupabaseStorageError(f"Error listing files: {e}") from e

    def get_file(self, bucket_name: str, file_path: str) -> Optional[bytes]:
        """Get file content from Supabase storage"""
        try:
            bucket = self.client.storage.from_(bucket_name)
            return bucket.download(file_path)
        except Exception as e:
            raise SupabaseStorageError(f"Error downloading file: {e}") from e

    def delete_file(self, bucket_name: str, file_path: str) -> bool:
        """Delete file from Supabase storage"""
        try:
            bucket = self.client.storage.from_(bucket_name)
            bucket.remove([file_path])
            return True  # If no exception was raised, deletion was successful
        except Exception as e:
            raise SupabaseStorageError(f"Error deleting file: {e}") from e