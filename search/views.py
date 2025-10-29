from django.http import JsonResponse
from .services import search_storage_files

def search_files(request):
    bucket = request.GET.get('bucket')
    term = request.GET.get('q')
    ext = request.GET.get('ext')
    
    if not bucket or not term:
        return JsonResponse({
            'error': 'Missing required parameters'
        }, status=400)
    
    try:
        results = search_storage_files(bucket, term, ext)
        return JsonResponse({'files': results})
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)