import json
from django.http import JsonResponse

def validate_payload(raw_body):
    """
    Validate JSON payload for CSV create/update

    Returns:
        dict: {'name': str, 'source_json': list/dict} if valid
        JsonResponse: error response if invalid
    """
    
    try:
        data = json.loads(raw_body)
    except json.JSONDecodeError:
        return None, JsonResponse({'error': 'Invalid JSON'}, status=400)

    name = data.get('name', '')
    if not isinstance(name, str) or not name.strip():
        return None, JsonResponse({'error': 'Name is required'}, status=400)

    source_json = data.get('source_json', None)
    if source_json is None:
        return None, JsonResponse({'error': 'source_json is required'}, status=400)

    return {'name': name.strip(), 'source_json': source_json}, None