from django.apps import AppConfig


class SaveToDatabaseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "save_to_database"

    def ready(self):
        from . import signals  # noqa: F401