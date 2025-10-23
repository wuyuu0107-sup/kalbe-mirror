import os
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CSV
from .utility.json_to_csv_bytes import json_to_csv_bytes
from .utility.upload_csv_to_supabase import upload_csv_to_supabase

logger = logging.getLogger(__name__)

@receiver(post_save, sender=CSV)
def convert_and_upload_csv(sender, instance: CSV, created, **kwargs):
    # Only proceed when there is JSON to convert
    if not instance.source_json:
        return

    # Skip automatic uploads in tests/CI unless explicitly enabled
    if os.getenv("SUPABASE_UPLOAD_ENABLED", "false").lower() not in ("1", "true", "yes"):
        logger.debug("Skipping upload: SUPABASE_UPLOAD_ENABLED not set")
        return

    bucket = os.getenv("SUPABASE_BUCKET_CSV")
    if not bucket:
        logger.warning("SUPABASE_BUCKET_CSV not set; skipping upload")
        return

    # PREVENT INFINITE RECURSION - skip if uploaded_url already exists
    if instance.uploaded_url:
        logger.debug("Upload URL already exists, skipping signal")
        return

    try:
        csv_bytes = json_to_csv_bytes(instance.source_json)
        if not csv_bytes:
            logger.warning("Converted CSV empty; skipping upload")
            return
        name = (instance.name or "csv").replace(" ", "_")
        pk = instance.id or "tmp"
        path = f"csvs/{pk}-{name}.csv"
        public_url = upload_csv_to_supabase(csv_bytes, bucket=bucket, path=path)
        if public_url:
            logger.info("Uploaded CSV for %s -> %s", instance, public_url)
            # Use update() to avoid triggering post_save again
            CSV.objects.filter(pk=instance.pk).update(uploaded_url=public_url)
    except Exception:
        logger.exception("Error converting/uploading CSV for %s", instance)