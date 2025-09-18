from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import render
from .utils import run_ocr_pipeline

def index(request):
    # Renders your HTML uploader at /api/ocr/
    return render(request, "ocr/index.html")

@csrf_exempt
@require_http_methods(["POST"])
def ocr_extract(request):
    """
    Accepts multipart/form-data with a single file field named 'file'
    (PNG/JPG/PDF) and returns JSON.
    """
    f = request.FILES.get("file")
    if not f:
        return JsonResponse({"error": "Upload a file with field name 'file'."}, status=400)

    try:
        # pass both bytes and name so utils can detect PDFs
        data = run_ocr_pipeline(f.read(), f.name)
        return JsonResponse(data, json_dumps_params={"indent": 2})
    except Exception as e:
        # Always return JSON so the frontend never crashes on HTML error pages
        return JsonResponse({"error": "OCR failed", "detail": str(e)}, status=500)
