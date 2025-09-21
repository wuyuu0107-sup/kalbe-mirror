from django.urls import path
from .views import ocr_image, ocr_test_page

app_name = "ocr"

urlpatterns = [
    path("", ocr_test_page, name="ocr_test_page"),
    path("image/", ocr_image, name="image"),
]
