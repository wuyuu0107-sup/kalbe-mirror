from django.urls import path
from .views import ocr_upload, ocr_endpoint

app_name = "ocr"

urlpatterns = [
    path("", ocr_endpoint, name="ocr"),
    path("upload/", ocr_upload, name="ocr_upload"),
]


