from django.urls import include, path
from .views import create_patient_from_data

urlpatterns = [
    path("create/", create_patient_from_data, name="create_patient"),
]
