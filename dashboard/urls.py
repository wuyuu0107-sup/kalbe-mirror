app_name = "dashboard"

from django.urls import path, include
from dashboard.views import recent_files_json, recent_features_json, whoami, breadcrumbs_json, ChatSuggestionViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'chat-suggestions', ChatSuggestionViewSet, basename='chat-suggestion')

urlpatterns = [
    path('api/', include(router.urls)),
    path("whoami/", whoami, name="whoami"),
    path("recent-files/<int:limit>/", recent_files_json, name="recent-files-json"),
    path("recent-files-json/<int:limit>/", recent_files_json, name="recent_files_json"),
    path("recent-features/", recent_features_json, name="recent-features-json"),
    path("recent-files-json/", recent_files_json, name="recent_files_json"),
    path("recent-features-json/", recent_features_json, name="recent_features_json"),
    path("breadcrumbs/", breadcrumbs_json, name="breadcrumbs"),
    path("user", whoami, name="whoami"),
]