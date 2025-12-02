import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit
from .models import Patient
from .utility.json_mapper import map_ocr_json_to_patient
from .validators import validate_patient_data

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
@ratelimit(key='ip', rate='100/h', method='POST', block=False)
def create_patient_from_data(request):
    """
    Create a Patient record from nested OCR JSON data.
    Maps nested structure to flat Patient model fields.
    
    Expected request body: JSON object with nested sections (DEMOGRAPHY, VITAL_SIGNS, etc.)
    
    Returns: JSON response with created patient ID and data
    """
    # Check if rate limited
    if getattr(request, 'limited', False):
        logger.warning(f"Patient creation rate limit exceeded for IP: {request.META.get('REMOTE_ADDR')}")
        return JsonResponse({
            'error': 'Too many requests. Please try again later.',
            'retry_after': '1 hour'
        }, status=429)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError as e:
        return JsonResponse({
            'error': 'Invalid JSON format',
            'message': str(e)
        }, status=400)
    
    try:
        patient_data = map_ocr_json_to_patient(data)
        
        # Enhanced input validation
        validation_errors = validate_patient_data(patient_data)
        if validation_errors:
            logger.warning(f"Patient data validation failed: {validation_errors}")
            return JsonResponse({
                'error': 'Validation failed',
                'details': validation_errors
            }, status=400)
        
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