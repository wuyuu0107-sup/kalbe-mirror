from django.contrib import admin
from .models import CSVFile


@admin.register(CSVFile)
class CSVFileAdmin(admin.ModelAdmin):
    list_display = ("id", "filename", "uploaded_at")
    readonly_fields = ("uploaded_at",)
    search_fields = ("file_path",)
    ordering = ("-uploaded_at",)
