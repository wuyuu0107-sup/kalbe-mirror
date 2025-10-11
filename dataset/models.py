from django.db import models

class CSVFile(models.Model):
    file_path = models.FileField(upload_to='csv_files/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.filename} ({self.uploaded_at:%Y-%m-%d %H:%M:%S})"

    @property
    def filename(self):
        import os
        return os.path.basename(self.file_path.name) if self.file_path else ""

    def delete(self, using=None, keep_parents=False):
        storage = self.file_path.storage
        name = self.file_path.name
        super().delete(using=using, keep_parents=keep_parents)
        if name:
            try:
                storage.delete(name)
            except Exception:
                # Ignore storage errors so delete doesn't crash
                pass
