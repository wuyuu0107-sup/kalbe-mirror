import json
import logging
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from .models import CSV
from .utility.json_to_csv_bytes import json_to_csv_bytes

logger = logging.getLogger(__name__)


def test_page(request):
    """Render the CSV conversion test page."""
    return render(request, 'test_page.html')


def save_converted_csv(name, json_data, file_obj=None):
    """
    Utility function to save JSON data as a CSV record.
    
    Args:
        name (str): Name for the CSV record
        json_data (list/dict): JSON data to convert
        file_obj (File, optional): Existing file object
    
    Returns:
        CSV: Created CSV record
    """
    try:
        # Convert JSON to CSV bytes
        csv_bytes = json_to_csv_bytes(json_data)
        
        # Create ContentFile with proper name
        csv_file = ContentFile(csv_bytes, name=f"{name}.csv")
        
        # Create the CSV record
        dataset = CSV.objects.create(
            name=name,
            file=csv_file,
            source_json=json_data
        )
        
        return dataset
        
    except Exception as e:
        logger.exception(f"Error saving converted CSV for {name}: {e}")
        raise


@csrf_exempt
def create_csv_record(request):
    """
    Create a new CSV record from JSON data.
    
    POST /save-to-database/create/
    {
        "name": "dataset-name",
        "source_json": [{"key": "value"}]
    }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    
        # Parse JSON data
    try:
            data = json.loads(request.body)
    except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        
        # Validate required fields
    name = data.get('name', '').strip()
    if not name:
            return JsonResponse({'error': 'Name is required'}, status=400)
        
    source_json = data.get('source_json')
    if source_json is None:
            return JsonResponse({'error': 'source_json is required'}, status=400)
        
        # Create CSV record using utility function
    try:
            csv_record = save_converted_csv(name, source_json)
            
            return JsonResponse({
                'id': csv_record.id,
                'name': csv_record.name,
                'file_url': csv_record.file.url if csv_record.file else None,
                'uploaded_url': csv_record.uploaded_url,
                'created_at': csv_record.created_at.isoformat()
            }, status=201)
            
    except Exception as e:
            logger.exception("Error creating CSV record")
            return JsonResponse({
                'error': 'Failed to create CSV record',
                'details': str(e)
            }, status=500)
            
