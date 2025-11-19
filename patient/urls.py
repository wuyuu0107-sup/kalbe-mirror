from django.urls import include, path
from .views import patient

urlpatterns = [
    path("patient/", patient, name="patient")
]
