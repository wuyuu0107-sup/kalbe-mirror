# audittrail/tests/urls_api.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

# 👇 import from your existing views.py
from audittrail.views import ActivityLogViewSet

router = DefaultRouter()
# this will expose /audit/logs/
router.register(r"audit/logs", ActivityLogViewSet, basename="audit-logs")

urlpatterns = [
    path("", include(router.urls)),
]
