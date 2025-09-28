import csv
import json
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .strategies import CSVExportStrategy
from django.contrib.auth.decorators import login_required

@login_required
@csrf_exempt
@require_POST
def export_csv(request):
    """
    Strategy Pattern Applied:
    - Uses CSVExportStrategy to handle the export algorithm
    - Strategy can be easily swapped for different export formats
    """
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
        export_strategy = CSVExportStrategy()
        export_strategy.export(data, writer)
    except Exception as e:
        return JsonResponse({
            'error': 'CSV conversion failed',
            'message': str(e)
        }, status=500)

    return response