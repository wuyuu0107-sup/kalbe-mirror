import os
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django_ratelimit.decorators import ratelimit
from notification.triggers import notify_ocr_completed, notify_ocr_failed
from dotenv import load_dotenv
from supabase import create_client, Client
from typing import Optional

logger = logging.getLogger(__name__)

from dashboard.tracking import track_feature
from ocr.services.gemini import GeminiService
from ocr.services.storage import StorageService
from ocr.services.document import DocumentService
from ocr.utils.spellchecker import correct_word
from ocr.utils.normalization import normalize_payload, order_sections
from ocr.utils.response_builders import build_success_response, build_error_response

@csrf_exempt
def health(request):
    return JsonResponse({"status": "ok"}, status=200)

@csrf_exempt
@track_feature("ocr")
@ratelimit(key='ip', rate='10/m', method='POST', block=False)
def ocr_test_page(request):
    load_dotenv()

    if request.method == "POST":
        # Check if rate limited
        if getattr(request, 'limited', False):
            logger.warning(f"OCR upload rate limit exceeded for IP: {request.META.get('REMOTE_ADDR')}")
            return JsonResponse({
                'error': 'Too many OCR requests. Please try again later.',
                'retry_after': '1 minute'
            }, status=429)
        
        return _handle_upload(request)
    
    return render(request, "ocr.html")

def _handle_upload(request):
    pdf_file = request.FILES.get("pdf")
    api_key = os.getenv("GEMINI_API_KEY")
    session_id = request.COOKIES.get("sessionid")
    user_id = request.session.get("user_id")
    
    if not pdf_file or not api_key:
        return build_error_response("Missing PDF or API key")
    
    try:
        supabase_client = _create_supabase_client()
        
        gemini_service = GeminiService(api_key)
        storage_service = StorageService(supabase_client)
        document_service = DocumentService()
        
        pdf_bytes = pdf_file.read()
        extracted_data = gemini_service.extract_medical_data(pdf_bytes)
        
        normalized_data = normalize_payload(extracted_data["parsed"])
        ordered_data = order_sections(normalized_data)
        
        local_pdf_url = storage_service.save_pdf_locally(pdf_file.name, pdf_bytes)
        supabase_urls = storage_service.upload_to_supabase(
            pdf_file.name, pdf_bytes, ordered_data
        )
        
        final_pdf_url = supabase_urls["pdf_url"] or local_pdf_url
        document, patient = document_service.create_document_and_patient(
            ordered_data, final_pdf_url, supabase_urls, local_pdf_url
        )
        
        if session_id:
            notify_ocr_completed(
                session_id,
                path=final_pdf_url,
                size=len(pdf_bytes),
                job_id=None,
                user_id=user_id
            )
        
        return build_success_response(
            document, patient, ordered_data, extracted_data, supabase_urls
        )
    
    except Exception as err:
        if session_id:
            notify_ocr_failed(
                session_id,
                path=pdf_file.name if pdf_file else "",
                reason=str(err),
                job_id=None,
            )

        return build_error_response(str(err))


def _create_supabase_client() -> Optional[Client]:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if SUPABASE_URL and SUPABASE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None