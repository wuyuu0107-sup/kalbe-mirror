from __future__ import annotations
from urllib.parse import unquote
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from authentication.models import User
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import ChatSuggestion
from .serializers import ChatSuggestionSerializer
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.authentication import SessionAuthentication, BasicAuthentication

class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return  # Disable CSRF

# Uncomment when being used
# from django.contrib.auth.decorators import login_required

# from .nav import try_label_annotation  # uncomment if you added it
from .nav import SEGMENT_LABELS, looks_like_id

# Services Import
from dashboard.services.recent_files import get_recent_files
from dashboard.services.feature_usage import get_recent_features

# Create your views here.

def whoami(request):
    return JsonResponse({
        "cookie_sessionid": request.COOKIES.get("sessionid"),
        "user_id": request.session.get("user_id"),
        "username": request.session.get("username"),
    })

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
    except (User.DoesNotExist, ValueError, ValidationError):
        return JsonResponse({"error": "User not found"}, status=404)

    items = get_recent_features(user)
    for it in items:
        if hasattr(it.get("last_used_at"), "isoformat"):
            it["last_used_at"] = it["last_used_at"].isoformat()
            
    return JsonResponse(items, safe=False)

# dashboard/views.py

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

        # 2) optional: dynamic lookup when the previous segment is 'annotation'
        # if not label and i > 0 and parts[i - 1] == "annotation":
        #     label = try_label_annotation(seg) or label

        # 3) default formatting
        if not label:
            label = seg if looks_like_id(seg) else seg.replace("-", " ").capitalize()

        crumbs.append({"href": href, "label": label})

    return JsonResponse(crumbs, safe=False)

class ChatSuggestionViewSet(viewsets.ModelViewSet):
    serializer_class = ChatSuggestionSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    authentication_classes = [CsrfExemptSessionAuthentication, BasicAuthentication]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return ChatSuggestion.objects.none()
        return ChatSuggestion.objects.filter(user_id=user.user_id)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)