from django.urls import path
from .views import handwriting_ocr

urlpatterns = [
    path("handwriting/", handwriting_ocr, name="handwriting_ocr"),
]