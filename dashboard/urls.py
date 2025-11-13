from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = "dashboard"

router = DefaultRouter()
router.register(r'chat-suggestions', views.ChatSuggestionViewSet, basename='chat-suggestion')

urlpatterns = [
    path('api/', include(router.urls)),
    path("user/", views.whoami, name="user"),
    path("whoami/", views.whoami, name="whoami"),
    path("recent-files/<int:limit>/", views.recent_files_json, name="recent-files-json"),
    path("recent-files-json/<int:limit>/", views.recent_files_json, name="recent_files_json"),
    path("recent-files-json/", views.recent_files_json, name="recent_files_json_no_limit"),
    path("recent-features/", views.recent_features_json, name="recent-features-json"),
    path("recent-features-json/", views.recent_features_json, name="recent_features_json"),
    path("breadcrumbs/", views.breadcrumbs_json, name="breadcrumbs"),
]