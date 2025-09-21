# ocr/views.py
import numpy as np
from PIL import Image
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from .reader import get_reader
from .utils import correct_word

def ocr_test_page(request):
    return render(request, "ocr_test.html")

def _json_default(o):
    """Fallback converter for any stray NumPy types."""
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    return str(o)

def _normalize_results(results):
    """(box, text, conf) -> dict with only plain Python types."""
    norm = []
    for box, text, conf in results:
        # Force to Python lists of floats to avoid int32
        b = np.asarray(box, dtype=float).tolist()
        norm.append({
            "box": b,
            "text": str(text),
            "confidence": float(conf),
        })
    return norm

@csrf_exempt
def ocr_image(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST an image file with the 'image' key.")

    f = request.FILES.get("image")
    if not f:
        return HttpResponseBadRequest("No file uploaded under 'image'.")

    try:
        img = Image.open(f).convert("RGB")
    except Exception:
        return HttpResponseBadRequest("Invalid image.")

    arr = np.array(img)
    reader = get_reader(langs=["en", "id"], gpu=False)
    results = reader.readtext(arr, detail=1, paragraph=False)

    payload = {"results": _normalize_results(results)}
    return JsonResponse(payload, json_dumps_params={"default": _json_default})

def _normalize_results(results):
    norm = []
    for box, text, conf in results:
        b = np.asarray(box, dtype=float).tolist()
        corrected = correct_word(str(text))
        norm.append({
            "box": b,
            "text": corrected,
            "confidence": float(conf),
        })
    return norm
