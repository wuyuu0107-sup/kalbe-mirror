from django.http import JsonResponse
from .services import search_storage_files

def search_files(request):
    # bucket is ignored for database-backed search
    term = request.GET.get('q')
    ext = request.GET.get('ext')

    if not term:
        return JsonResponse({
            'error': 'Missing required parameter: q (search term)'
        }, status=400)

    try:
        # Pass dummy bucket for compatibility
        results = search_storage_files('unused', term, ext)
        return JsonResponse({'files': results})
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)