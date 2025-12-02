import logging
from django.http import JsonResponse
from .services import search_storage_files
from patient.validators import validate_search_query

logger = logging.getLogger(__name__)

def search_files(request):
    # bucket is ignored for database-backed search
    term = request.GET.get('q')
    ext = request.GET.get('ext')

    # Validate search query
    validation_error = validate_search_query(term, ext)
    if validation_error:
        logger.warning(f"Search validation failed: {validation_error} from IP {request.META.get('REMOTE_ADDR')}")
        return JsonResponse(validation_error, status=400)

    try:
        # Pass dummy bucket for compatibility
        results = search_storage_files('unused', term, ext)
        return JsonResponse({'files': results})
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)