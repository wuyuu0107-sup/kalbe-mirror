import json
from typing import Dict, Any

from django.http import HttpResponse

from annotation.models import Document
from patient.models import Patient   # 👈 use your real Patient app here


def build_success_response(
    document: Document,
    patient: Patient,
    ordered_data: Dict[str, Any],
    extracted_data: Dict[str, Any],
    supabase_urls: Dict[str, str],
) -> HttpResponse:
    result = {
        "success": True,
        "error": None,
        "processing_time": extracted_data["processing_time"],
        "document_id": document.id,
        "patient_id": patient.id,
        "pdf_url": document.content_url,
        "structured_data": ordered_data,
        "raw_response": extracted_data["raw_text"],
        "storage_json_url": supabase_urls["json_url"],
    }
    return HttpResponse(json.dumps(result), content_type="application/json")


def build_error_response(error_message: str) -> HttpResponse:
    result = {
        "success": False,
        "error": error_message,
        "processing_time": 0,
        "structured_data": {},
        "raw_response": "",
    }
    return HttpResponse(
        json.dumps(result),
        content_type="application/json",
        status=200,
    )
