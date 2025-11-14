app_name = "dashboard"

from django.urls import path, include
from .views import recent_files_json, recent_features_json, whoami, ChatSuggestionViewSet
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'chat-suggestions', ChatSuggestionViewSet, basename='chat-suggestion')

urlpatterns = [
    path('api/', include(router.urls)),
    path("whoami/", views.whoami, name="whoami"),
    path("recent-files/<int:limit>/", views.recent_files_json, name="recent-files-json"),
    path("recent-files-json/<int:limit>/", views.recent_files_json, name="recent_files_json"),
    path("recent-features/", views.recent_features_json, name="recent-features-json"),
    path("recent-files-json/", views.recent_files_json, name="recent_files_json"),
    path("recent-features-json/", views.recent_features_json, name="recent_features_json"),
    path("breadcrumbs/", views.breadcrumbs_json, name="breadcrumbs"),
    path("user", whoami, name="whoami"),
]