import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from supabase import create_client

BUCKET = os.getenv("SUPABASE_CSV_BUCKET", "csv")
FOLDER = os.getenv("SUPABASE_CSV_FOLDER", "csvs")
    
class NullStorage:
    def list_csv(self):
        return []

class SupabaseCSVStorage:
    def __init__(self, url: str, key: str, bucket: str = BUCKET, folder: str = FOLDER):
        if create_client is None:
            raise RuntimeError("supabase client not available; install `supabase` package")
        self.bucket = bucket
        self.folder = folder
        self.cli = create_client(url, key)
        self._storage = self.cli.storage.from_(bucket)
    
    def list_csv(self):
        objs = self._storage.list(self.folder) or []
        objs.sort(key=lambda o: o["name"], reverse=True)
        objs = objs[:10]

        out: List[Dict[str, Any]] = []

        for o in objs:
            name = o.get("name") or ""
            if not name:
                continue
            path = f"{self.folder}/{name}"
            updated_at = o.get("updated_at") or o.get("last_accessed_at") or o.get("created_at")
            size = o.get("size") or (o.get("metadata") or {}).get("size")
            out.append(
                {
                    "name": name,
                    "path": path,
                    "bucket": self.bucket,
                    "size": size,
                    "updated_at": updated_at,
                }
            )
        return out

def get_storage():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if url and key:
        try:
            return SupabaseCSVStorage(url, key)
        except Exception as e:
            # If supabase client missing/misconfigured, fail safe
            return NullStorage()
    return NullStorage()