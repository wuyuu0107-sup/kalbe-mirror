import os
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CSV
from .utility.json_to_csv_bytes import json_to_csv_bytes
from .utility.upload_csv_to_supabase import upload_csv_to_supabase
import datetime

logger = logging.getLogger(__name__)

@receiver(post_save, sender=CSV)
def convert_and_upload_csv(sender, instance: CSV, created, **kwargs):
    if not instance.source_json:
        return
    
    if not instance.file.name.lower().endswith('.csv'):
        logger.debug(f"Skipping upload for non-CSV file: {instance.file.name}")
        return


    if os.getenv("SUPABASE_UPLOAD_ENABLED", "false").lower() not in ("1", "true", "yes"):
        logger.debug("Skipping upload: SUPABASE_UPLOAD_ENABLED not set")
        return

    bucket = os.getenv("SUPABASE_BUCKET_CSV")
    if not bucket:
        logger.warning("SUPABASE_BUCKET_CSV not set; skipping upload")
        return

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
        dt = datetime.datetime.now().date()
        path = f"csvs/{dt}_{pk}_{name}.csv"
        public_url = upload_csv_to_supabase(csv_bytes, bucket=bucket, path=path)
        if public_url:
            logger.info("Uploaded CSV for %s -> %s", instance, public_url)
            # Use update() to avoid triggering post_save again
            CSV.objects.filter(pk=instance.pk).update(uploaded_url=public_url)
    except Exception:
        logger.exception("Error converting/uploading CSV for %s", instance)