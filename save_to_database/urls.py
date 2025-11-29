from django.urls import path
from . import views

app_name = "save_to_database"

urlpatterns = [
    path("create/", views.create_csv_record, name="create_csv_record"),
    path("update/<int:pk>/", views.update_csv_record, name="update_csv_record"),
    path("delete/<int:pk>/", views.delete_csv_record, name="delete_csv_record"),
]