# audittrail/tests/urls.py
from django.http import JsonResponse
from django.urls import path


def ok(request, *args, **kwargs):
    return JsonResponse({"ok": True})


urlpatterns = [
    path("auth/login/", ok),
    path("ocr/", ok),
    path("dashboard/recent-features/", ok),
    path("save-to-database/create/", ok),
    path("api/v1/comments/", ok),
    path("api/v1/annotations/", ok),
    path("api/v1/documents/123/", ok),
    path("auth/api/protected-endpoint/", ok),
]
