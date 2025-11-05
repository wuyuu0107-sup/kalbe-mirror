app_name = "dashboard"

from django.urls import path, include
from .views import recent_files_json, recent_features_json, whoami, ChatSuggestionViewSet
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'chat-suggestions', ChatSuggestionViewSet, basename='chat-suggestion')

urlpatterns = [
    path('api/', include(router.urls)),

    path("recent-files/<int:limit>/", recent_files_json, name="recent-files-json"),
    path("recent-features/", recent_features_json, name="recent-features-json"),
    path("breadcrumbs/", views.breadcrumbs_json, name="breadcrumbs"),
    path("breadcrumbs_demo/", views.breadcrumbs_demo, name="breadcrumbs_demo"),
    path("user", whoami, name="whoami"),
]