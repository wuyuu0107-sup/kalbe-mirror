from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@require_POST
def register(request):
    # SKELETON implementation
    return JsonResponse({"error": "not implemented"}, status=501)

