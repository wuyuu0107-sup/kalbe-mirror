from django.contrib import admin
from save_to_database.models import CSV


@admin.register(CSV)
class CSVAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at")
    readonly_fields = ("created_at",)
    search_fields = ("name", "file")
    ordering = ("-created_at",)
