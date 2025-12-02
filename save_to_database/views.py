import json
import logging
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.base import ContentFile
from .models import CSV
from save_to_database.utility.json_to_csv_bytes import json_to_csv_bytes
from save_to_database.utility.validate_payload import validate_payload


logger = logging.getLogger(__name__)

# Helper Function
def csv_to_response(csv_obj):
    return {
        'id': csv_obj.id,
        'name': csv_obj.name,
        'file_url': csv_obj.file.url if csv_obj.file else None,
        'uploaded_url': csv_obj.uploaded_url,
        'created_at': csv_obj.created_at.isoformat()
    }


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
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)

    payload, error_response = validate_payload(request.body)
    if error_response:
        return error_response

    try:
        csv_record = save_converted_csv(payload['name'], payload['source_json'])
        return JsonResponse(csv_to_response(csv_record), status=201)

    except Exception as e:
        logger.exception("Error creating CSV record")
        return JsonResponse({'error': 'Failed to create CSV record', 'details': str(e)}, status=500)


def update_converted_csv(instance: CSV, name: str, json_data):
    """
    Update an existing CSV file with new JSON data and overwrite it. Returns updated file.
    """
    try:
        # convert
        csv_bytes = json_to_csv_bytes(json_data)
        csv_file = ContentFile(csv_bytes, name=f"{name}.csv")

        # update fields
        instance.name = name
        instance.source_json = json_data
        instance.file.save(csv_file.name, csv_file, save=False)  # replace stored file

        # clear uploaded_url since file changed
        instance.uploaded_url = None

        instance.save()
        return instance
    except Exception as e:
        logger.exception(f"Error updating converted CSV for {name}: {e}")
        raise


@csrf_exempt
def update_csv_record(request, pk):
    if request.method != 'PUT':
        return JsonResponse({'error': 'Only PUT allowed'}, status=405)

    payload, error_response = validate_payload(request.body)
    if error_response:
        return error_response

    instance = get_object_or_404(CSV, pk=pk)

    try:
        updated = update_converted_csv(
            instance, payload['name'], payload['source_json']
        )

        return JsonResponse(csv_to_response(updated), status=200)

    except Exception as e:
        logger.exception("Error updating CSV record")
        return JsonResponse({'error': 'Failed to update CSV record', 'details': str(e)}, status=500)
    

@csrf_exempt
def delete_csv_record(request, pk):

    """Delete an existing CSV record and its associated file."""
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Only DELETE method allowed'}, status=405)


    instance = get_object_or_404(CSV, pk=pk)


    try:
        if instance.file:
            instance.file.delete(save=False)
        instance.delete()
        logger.info(f"CSV record {pk} deleted successfully")
        return JsonResponse({'message': f'CSV record {pk} deleted successfully.'}, status=200)
    
    except Exception as e:
        logger.exception("Error deleting CSV record")
        return JsonResponse({'error': 'Failed to delete CSV record', 'details': str(e)}, status=500)