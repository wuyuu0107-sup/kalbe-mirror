# audittrail/tests/urls.py
from django.http import JsonResponse
from django.urls import path


def ok(request, *args, **kwargs):
    return JsonResponse({"ok": True})


def bad(request, *args, **kwargs):
    return JsonResponse({"error": True}, status=400)


urlpatterns = [
    path("auth/login/", ok),
    path("ocr/", ok),
    path("dashboard/recent-features/", ok),
    path("save-to-database/create/", ok),
    path("api/v1/comments/", ok),
    path("api/v1/annotations/", ok),
    path("api/v1/documents/123/", ok),
    path("auth/api/protected-endpoint/", ok),

    # new ones for coverage
    path("some-random-path/", ok),
    path("will-return-400/", bad),
    path("api/chat/something/", ok),
]
