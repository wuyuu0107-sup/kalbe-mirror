import csv
import json
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from csv_export.utility.json_to_csv import *

@csrf_exempt
@require_POST
def export_csv(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        return JsonResponse({
            'error': 'Invalid JSON format',
            'message': str(e)
        }, status=400)
    except ValueError as e:
        return JsonResponse({
            'error': 'Invalid request body',
            'message': str(e)
        }, status=400)

    response = HttpResponse(content_type="text/csv")
    response['Content-Disposition'] = 'attachment; filename="report.csv"'

    writer = csv.writer(response)
    
    try:
        json_to_csv(data, writer)
    except Exception as e:
        return JsonResponse({
            'error': 'CSV conversion failed',
            'message': str(e)
        }, status=500)

    return response