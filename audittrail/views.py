# audittrail/views.py
from django.http import JsonResponse


def ping(request):
    return JsonResponse({"status": "ok"})

# audittrail/views_logviewer.py
from datetime import datetime

from django.utils.timezone import make_aware
from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import SearchFilter, OrderingFilter

from django_filters.rest_framework import DjangoFilterBackend
import django_filters

from audittrail.models import ActivityLog
from audittrail.serializers import ActivityLogSerializer
from rest_framework.permissions import AllowAny



class ActivityLogPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200  # prevent giant blob


class ActivityLogFilter(django_filters.FilterSet):
    # /api/audit/logs/?date_from=2025-11-08&date_to=2025-11-09
    date_from = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    date_to = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = ActivityLog
        fields = ["event_type", "username"]  # exact matches


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET /api/audit/logs/
    GET /api/audit/logs/?username=userhafizh
    GET /api/audit/logs/?event_type=ANNOTATION_UPDATED
    GET /api/audit/logs/?date_from=2025-11-08T00:00:00Z&date_to=2025-11-09T23:59:59Z
    GET /api/audit/logs/?search=annotations
    """
    queryset = ActivityLog.objects.all().order_by("-created_at")
    serializer_class = ActivityLogSerializer
    pagination_class = ActivityLogPagination
    permission_classes = [AllowAny]  # tighten if needed

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]
    filterset_class = ActivityLogFilter
    search_fields = [
        "username",
        "event_type",
        "target_repr",
        "metadata",  # JSONField, DRF can still do icontains on PG JSONB
    ]
    ordering_fields = ["created_at", "id"]
    ordering = ["-created_at"]
