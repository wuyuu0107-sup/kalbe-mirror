# from django.shortcuts import render
from django.http import JsonResponse
from .services.recent_files import get_recent_files
# Create your views here.

def recent_files_json(request):
    items = get_recent_files()
    for i in items:
        if hasattr(i.get("updated_at"), "isoformat"):
            i["updated_at"] = i["updated_at"].isoformat()
        
    return JsonResponse(items, safe=False)