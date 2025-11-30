import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from .models import Patient
from .utility.json_mapper import map_ocr_json_to_patient

@csrf_exempt
@require_POST
def create_patient_from_data(request):
    """
    Create a Patient record from nested OCR JSON data.
    Maps nested structure to flat Patient model fields.
    
    Expected request body: JSON object with nested sections (DEMOGRAPHY, VITAL_SIGNS, etc.)
    
    Returns: JSON response with created patient ID and data
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        return JsonResponse({
            'error': 'Invalid JSON format',
            'message': str(e)
        }, status=400)
    
    try:
        patient_data = map_ocr_json_to_patient(data)
        
        patient = Patient.objects.create(**patient_data)
        
        return JsonResponse({
            'success': True,
            'patient_id': patient.id,
            'patient': {
                'subject_initials': patient.subject_initials,
                'gender': patient.gender,
                'age': patient.age,
            }
        }, status=201)
        
    except Exception as e:
        return JsonResponse({
            'error': 'Failed to create patient',
            'message': str(e),
            'type': type(e).__name__
        }, status=500)