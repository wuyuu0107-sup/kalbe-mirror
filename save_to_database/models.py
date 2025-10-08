from django.db import models

class CSV(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='datasets/csvs/')
    created_at = models.DateTimeField(auto_now_add=True)
    source_json = models.JSONField(blank=True, null=True)
    record_count = models.IntegerField(default=0)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name
