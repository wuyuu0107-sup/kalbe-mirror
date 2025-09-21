from django.urls import path
from .views import ocr_image, ocr_test_page

app_name = "ocr"

urlpatterns = [
    path("", ocr_image, name="image"),         
    path("test/", ocr_test_page, name="test"),  
]
