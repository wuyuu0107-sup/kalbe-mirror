from django.urls import include, path
from .views import ocr_image, ocr_test_page, health, api_ocr

app_name = "ocr"

urlpatterns = [
    path("health/", health, name="health"),
    path("", ocr_test_page, name="ocr_test_page"),
    path("image/", ocr_image, name="image"),
    path("api/ocr/", api_ocr, name="api_ocr"),
    path('csv/', include('csv_export.urls'))
]
