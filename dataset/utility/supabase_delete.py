import os
import logging
from typing import Optional
from urllib.parse import urlparse, unquote
from supabase import create_client

logger = logging.getLogger(__name__)

def delete_supabase_file(uploaded_url: Optional[str]) -> bool:
    """
    Delete a file from the Supabase storage bucket given the uploaded URL.

    Returns True if the delete was successfully attempted, False otherwise.

    Handles public URLs, query strings, URL-encoded characters, and checks
    the Supabase remove() response for errors.
    """
    if not uploaded_url:
        return False

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET_CSV")

    if not (SUPABASE_URL and SUPABASE_KEY and SUPABASE_BUCKET):
        logger.debug("Supabase credentials or bucket missing; skipping delete")
        return False

    try:
        client = create_client(SUPABASE_URL, SUPABASE_KEY)

        path = uploaded_url

        # If the URL is public, extract the storage path
        if isinstance(path, str) and path.startswith("http"):
            parsed = urlparse(path)
            raw_path = unquote(parsed.path)  # removes query string & decodes %20
            marker = "/storage/v1/object/public/"
            if marker in raw_path:
                tail = raw_path.split(marker, 1)[1]  # "{bucket}/path/to/file"
                # Remove bucket prefix if present
                if tail.startswith(SUPABASE_BUCKET + "/"):
                    path = tail[len(SUPABASE_BUCKET) + 1 :]
                else:
                    # fallback: remove first path segment
                    parts = tail.split("/", 1)
                    path = parts[1] if len(parts) > 1 else parts[0]
            else:
                # fallback: take last segment as best effort
                path = raw_path.lstrip("/").split("/")[-1]

        # Normalize path
        path = path.strip().lstrip("/")

        if not path:
            logger.debug("Could not determine storage path from uploaded_url=%r", uploaded_url)
            return False

        logger.debug("Attempting to delete from bucket=%s path=%s", SUPABASE_BUCKET, path)

        res = client.storage.from_(SUPABASE_BUCKET).remove([path])

        # Supabase client returns dict with 'error' or 'message'
        error = None
        if isinstance(res, dict):
            error = res.get("error") or res.get("message")
        else:
            error = getattr(res, "error", None) or getattr(res, "message", None)

        logger.debug("Supabase remove response: %r", res)

        if error:
            logger.error("Supabase remove failed: %r", error)
            return False

        return True

    except Exception:
        logger.exception("Error creating Supabase client or deleting file")
        return False
