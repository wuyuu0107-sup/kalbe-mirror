# from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

# Services Import
from dashboard.services.recent_files import get_recent_files
from dashboard.services.feature_usage import get_recent_features

# Create your views here.

def recent_files_json(request):
    items = get_recent_files()
    for i in items:
        if hasattr(i.get("updated_at"), "isoformat"):
            i["updated_at"] = i["updated_at"].isoformat()
        
    return JsonResponse(items, safe=False)

def recent_features_json(request):
    items = get_recent_features(request.user)
    for it in items:
        if hasattr(it.get("last_used_at"), "isoformat"):
            it["last_used_at"] = it["last_used_at"].isoformat()
            
    return JsonResponse(items, safe=False)