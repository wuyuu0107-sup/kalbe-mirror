from django.urls import path
from dashboard.views import recent_files_json

app_name = "dashboard"
urlpatterns = [
    path("recent-files/", recent_files_json, name="recent-files-json"),
]
