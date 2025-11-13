# Place this file at:
# c:\Users\ASUS\Documents\1.UNIVERSITY\SEM 5\PPL\BackEnd\kalbe_be\save_to_database\utils.py
# ...existing code...
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def upload_csv_to_supabase(csv_bytes: bytes, bucket: str, path: str) -> Optional[str]:
    """
    Upload CSV bytes to Supabase storage and return public URL or path.
    No-op when SUPABASE_UPLOAD_ENABLED is not set (safe for tests/CI).
    """
    if os.getenv("SUPABASE_UPLOAD_ENABLED", "false").lower() not in ("1", "true", "yes"):
        logger.info("Supabase upload disabled by SUPABASE_UPLOAD_ENABLED")
        return None

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.warning("Supabase credentials missing; skipping upload")
        return None

    try:
        from supabase import create_client
    except Exception:
        logger.exception("supabase package not available")
        return None

    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    try:
        client.storage.from_(bucket).upload(path, csv_bytes, {"contentType": "text/csv", "upsert": "true"})
    except Exception:
        try:
            client.storage.from_(bucket).upload(path, csv_bytes)
        except Exception:
            logger.exception("Supabase upload failed")
            return None

    pub = client.storage.from_(bucket).get_public_url(path)
    if isinstance(pub, dict):
            return pub.get("publicURL") or pub.get("public_url")
    if isinstance(pub, str):
            return pub

    return path