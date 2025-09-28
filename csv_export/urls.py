from django.urls import include, path
from .views import export_csv

app_name = "ocr"

urlpatterns = [
    path("export/", export_csv, name="export_csv")
]
