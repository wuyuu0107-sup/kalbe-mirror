from django.urls import path
from .views import ocr_test_page, health, api_ocr

app_name = "ocr"

urlpatterns = [
    path("health/", health, name="health"),
    path("", ocr_test_page, name="ocr_test_page"),
    path("api/ocr/", api_ocr, name="api_ocr"),
]
