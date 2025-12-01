from __future__ import annotations
from urllib.parse import unquote

from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from django.core.exceptions import ValidationError as DjangoValidationError

from authentication.models import User
from django.views.decorators.csrf import csrf_exempt

from rest_framework import viewsets
from rest_framework.permissions import BasePermission
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
from rest_framework.exceptions import PermissionDenied

from .models import ChatSuggestion
from .serializers import ChatSuggestionSerializer

from .nav import SEGMENT_LABELS, looks_like_id

# Services Import
from dashboard.services.recent_files import get_recent_files
from dashboard.services.feature_usage import get_recent_features


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """SessionAuthentication tanpa cek CSRF DRF (kita pakai cookie session)."""
    def enforce_csrf(self, request):
        return  # Disable CSRF checks for DRF


class HasSessionUser(BasePermission):
    """
    Permission DRF yang menganggap user 'authenticated'
    kalau di session ada 'user_id' (sesuai skema login app ini).
    """
    def has_permission(self, request, view):
        return bool(request.session.get("user_id"))


# ----------------- Simple JSON helpers ----------------- #

def whoami(request):
    return JsonResponse(
        {
            "cookie_sessionid": request.COOKIES.get("sessionid"),
            "user_id": request.session.get("user_id"),
            "username": request.session.get("username"),
        }
    )


@csrf_exempt
def recent_files_json(request, limit):
    try:
        items = get_recent_files(limit)
        print("DEBUG: get_recent_files() returned:", items)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

    for i in items:
        if hasattr(i.get("updated_at"), "isoformat"):
            i["updated_at"] = i["updated_at"].isoformat()

    return JsonResponse(items, safe=False)


def recent_features_json(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        user = User.objects.get(user_id=user_id)
    except (User.DoesNotExist, ValueError, DjangoValidationError):
        return JsonResponse({"error": "User not found"}, status=404)

    items = get_recent_features(user)
    for it in items:
        if hasattr(it.get("last_used_at"), "isoformat"):
            it["last_used_at"] = it["last_used_at"].isoformat()

    return JsonResponse(items, safe=False)


def breadcrumbs_json(request):
    """
    GET /dashboard/breadcrumbs/?path=/annotation/123/edit
    Returns:
    [
      {"href": "/", "label": "Home"},
      {"href": "/annotation", "label": "Annotations"},
      {"href": "/annotation/123", "label": "123" | model title},
      {"href": "/annotation/123/edit", "label": "Edit"}
    ]
    """
    path = request.GET.get("path")
    if not path:
        return HttpResponseBadRequest('Missing "path" query param')
    path = unquote(path)

    parts = [p for p in path.split("/") if p]  # drop empty segments
    crumbs = [{"href": "/", "label": "Home"}]

    for i, seg in enumerate(parts):
        href = "/" + "/".join(parts[: i + 1])

        # 1) known segment label?
        label = SEGMENT_LABELS.get(seg)

        # 3) default formatting
        if not label:
            label = seg if looks_like_id(seg) else seg.replace("-", " ").capitalize()

        crumbs.append({"href": href, "label": label})

    return JsonResponse(crumbs, safe=False)


# ----------------- Chat Suggestions API ----------------- #

class ChatSuggestionViewSet(viewsets.ModelViewSet):
    """
    /dashboard/api/chat-suggestions/

    - Pakai session-based auth (user_id di request.session)
    - Frontend Next mesti call dengan `credentials: "include"`
      supaya cookie session ikut.
    """
    serializer_class = ChatSuggestionSerializer
    authentication_classes = [CsrfExemptSessionAuthentication, BasicAuthentication]
    permission_classes = [HasSessionUser]

    def _get_user_from_session(self) -> User:
        user_id = self.request.session.get("user_id")
        if not user_id:
            # Kalau sampai sini, berarti permission salah / dipanggil tanpa login
            raise PermissionDenied("Unauthorized")

        try:
            return User.objects.get(user_id=user_id)
        except User.DoesNotExist:
            raise PermissionDenied("Unauthorized")

    def get_queryset(self):
        try:
            user = self._get_user_from_session()
        except PermissionDenied:
            return ChatSuggestion.objects.none()
        return ChatSuggestion.objects.filter(user=user).order_by("id")

    def perform_create(self, serializer):
        user = self._get_user_from_session()
        serializer.save(user=user)

    def perform_update(self, serializer):
        # Pastikan ownership tetap user di session
        user = self._get_user_from_session()
        serializer.save(user=user)

    def perform_destroy(self, instance):
        user = self._get_user_from_session()
        if instance.user_id != user.id:
            # Jangan kasih tau terlalu detail, treat as forbidden
            raise PermissionDenied("Cannot delete other user's suggestion")
        instance.delete()
