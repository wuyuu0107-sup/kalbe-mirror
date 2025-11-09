import os
import re
import json
import time
import mimetypes
import logging
from typing import Dict, Any, Optional
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from supabase import Client

logger = logging.getLogger(__name__)


class StorageService:
    
    def __init__(self, supabase_client: Optional[Client] = None):
        self.supabase = supabase_client
        self.bucket_name = os.getenv("SUPABASE_BUCKET", "ocr")
    
    def save_pdf_locally(self, filename: str, pdf_bytes: bytes) -> str:
        local_save_path = f"ocr/{filename}"
        stored_path = default_storage.save(local_save_path, ContentFile(pdf_bytes))
        
        try:
            return default_storage.url(stored_path)
        except Exception:
            return (settings.MEDIA_URL.rstrip("/") + "/" + stored_path.lstrip("/"))
    
    def upload_to_supabase(
        self,
        filename: str,
        pdf_bytes: bytes,
        ordered_data: Dict[str, Any]
    ) -> Dict[str, Optional[str]]:
        if not self.supabase:
            return {"pdf_url": None, "json_url": None}
        
        storage = self.supabase.storage.from_(self.bucket_name)
        storage_path = self._generate_storage_path(filename)
        
        pdf_url = self._upload_pdf_to_storage(storage, storage_path, pdf_bytes, filename)
        json_url = self._upload_json_to_storage(storage, storage_path, ordered_data)
        
        return {"pdf_url": pdf_url, "json_url": json_url}
    
    def _generate_storage_path(self, filename: str) -> str:
        ts = int(time.time())
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", filename)
        return f"{ts}_{safe_name}"
    
    def _upload_pdf_to_storage(self, storage, storage_path: str, pdf_bytes: bytes, filename: str) -> Optional[str]:
        content_type = mimetypes.guess_type(filename)[0] or "application/pdf"
        file_opts = {"contentType": content_type, "upsert": "true"}
        
        storage.upload(path=storage_path, file=pdf_bytes, file_options=file_opts)
        
        try:
            signed_res = storage.create_signed_url(storage_path, 60 * 60)
            return self._extract_url_from_response(signed_res)
        except Exception as e:
            logger.warning("Failed to create signed URL for %s: %s", storage_path, e)
            return None
    
    def _upload_json_to_storage(self, storage, storage_path: str, ordered_data: Dict[str, Any]) -> Optional[str]:
        json_bytes = json.dumps(
            ordered_data,
            ensure_ascii=False,
            separators=(",", ":"),
            indent=2
        ).encode("utf-8")
        
        json_path = storage_path.rsplit(".", 1)[0] + ".json"
        json_opts = {"contentType": "application/json", "upsert": "true"}
        
        storage.upload(path=json_path, file=json_bytes, file_options=json_opts)
        
        try:
            pub_json = storage.get_public_url(json_path)
            return self._extract_url_from_response(pub_json)
        except Exception:
            try:
                signed_json = storage.create_signed_url(json_path, 7 * 24 * 3600)
                return self._extract_url_from_response(signed_json)
            except Exception:
                return None
    
    def _extract_url_from_response(self, val) -> Optional[str]:
        if isinstance(val, str):
            return val.rstrip("?")
        if isinstance(val, dict):
            url = (
                val.get("signedURL")
                or val.get("signed_url")
                or val.get("publicURL")
                or val.get("public_url")
                or val.get("url")
            )
            return url.rstrip("?") if url else None
        return None