from django.urls import path
from dashboard.views import recent_files_json, recent_features_json

app_name = "dashboard"
urlpatterns = [
    path("recent-files/", recent_files_json, name="recent-files-json"),
    path("recent-features/", recent_features_json, name="recent-features-json"),
]
