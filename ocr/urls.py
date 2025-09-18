from django.urls import path
from .views import ocr_extract, index

urlpatterns = [
    path("", index, name="ocr_index"),
    path('extract/', ocr_extract, name='ocr_extract'),
]