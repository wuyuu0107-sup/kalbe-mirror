from django.urls import path
from . import views

app_name = "save_to_database"

urlpatterns = [
    path("", views.test_page, name="test_page"),
    path("create/", views.create_csv_record, name="create_csv_record"),
]