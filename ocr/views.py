import os
import re
import time
import json

from django.http import HttpResponseBadRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
import google.generativeai as genai
from dotenv import load_dotenv

from .reader import get_reader
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from .utils import correct_word
from django.conf import settings


# --- PDF support flag for tests / optional dependency ---
try:
    import fitz  # PyMuPDF
    HAS_PDF = True
except ImportError:
    fitz = None  # type: ignore
    HAS_PDF = False


@csrf_exempt
def api_ocr(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST an image or PDF file with the 'file' key.")

    f = request.FILES.get("file")
    if not f:
        return JsonResponse({"error": "No file uploaded under 'file'."}, status=400)

    file_ext = os.path.splitext(f.name)[1].lower()

    if file_ext == ".pdf":
        if not HAS_PDF:
            return JsonResponse({"error": "PDF support not available"}, status=500)
        try:
            pdf_bytes = f.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[arg-type]
        except Exception:
            # Keep 200 per your current behavior if invalid PDF when HAS_PDF available
            return JsonResponse({"error": "Invalid PDF.", "success": False}, status=200)

        pages = []
        for idx in range(doc.page_count):
            page = doc.load_page(idx)
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            arr = np.array(img)
            reader = easyocr.Reader(["en", "id"], gpu=False)
            text = "\n".join(t[1] for t in reader.readtext(arr, detail=1, paragraph=False))
            pages.append({"text": text})

        result = {
            "filename": f.name,
            "method": "ocr",
            "pages": pages,
            "success": True,
            "error": None,
        }
        return JsonResponse(result)

    elif file_ext in [".png", ".jpg", ".jpeg"]:
        try:
            img = Image.open(f).convert("RGB")
        except Exception:
            return JsonResponse({"error": "Invalid image."}, status=400)

        arr = np.array(img)
        reader = easyocr.Reader(["en", "id"], gpu=False)
        text = "\n".join(t[1] for t in reader.readtext(arr, detail=1, paragraph=False))
        result = {
            "filename": f.name,
            "method": "ocr",
            "pages": [{"text": text}],
            "success": True,
            "error": None,
        }
        return JsonResponse(result)

    else:
        return JsonResponse({"error": "Unsupported file type."}, status=400)


@csrf_exempt
def health(request):
    return JsonResponse({"status": "ok"}, status=200)


from annotation.models import Document, Patient

@csrf_exempt
def ocr_test_page(request):
    load_dotenv()
    if request.method == "POST":
        pdf_file = request.FILES.get("pdf")
        api_key = os.getenv("GEMINI_API_KEY")
        result: dict = {}
        if pdf_file and api_key:
            try:
                # 1) Call Gemini 2.5 OCR
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-2.5-flash")
                prompt = """
                Analyze this medical document PDF and extract the following information in JSON format.
                If any information is not found, leave the value as null. Some labels are Indonesian (e.g., "berat jenis" for urine density).
                For urinalysis, hematology, and clinical chemistry, return objects with keys:
                "Hasil", "Nilai Rujukan", "Satuan", "Metode".
                Required Fields:
                1. DEMOGRAPHY:
                   - subject_initials
                   - sin
                   - study_drug
                   - screening_date
                   - gender
                   - date_of_birth
                   - age
                   - weight_kg
                   - height_cm
                   - bmi
                2. MEDICAL_HISTORY:
                   - smoker_cigarettes_per_day
                3. VITAL_SIGNS:
                   - systolic_bp
                   - diastolic_bp
                   - heart_rate
                4. SEROLOGY:
                   - hbsag
                   - hcv
                   - hiv
                5. URINALYSIS:
                   - ph
                   - density
                   - glucose
                   - ketone
                   - urobilinogen
                   - bilirubin
                   - blood
                   - leucocyte_esterase
                   - nitrite
                6. HEMATOLOGY:
                   - hemoglobin
                   - hematocrit
                   - leukocyte
                   - erythrocyte
                   - thrombocyte
                   - esr
                7. CLINICAL_CHEMISTRY:
                   - bilirubin_total
                   - alkaline_phosphatase
                   - sgot
                   - sgpt
                   - ureum
                   - creatinine
                   - random_blood_glucose
                Provide ONLY a single JSON object with those sections/keys.
                """.strip()

                pdf_bytes = pdf_file.read()
                t0 = time.time()
                resp = model.generate_content(
                    [prompt, {"mime_type": "application/pdf", "data": pdf_bytes}],
                    generation_config={"temperature": 0},
                )
                dt = round(time.time() - t0, 2)

                # 2) Clean + parse JSON
                text = (resp.text or "").strip()
                text = re.sub(r"^```json\s*", "", text, flags=re.M)
                text = re.sub(r"^```\s*", "", text, flags=re.M)
                text = re.sub(r"\s*```$", "", text)
                try:
                    extracted = json.loads(text)
                except Exception:
                    # last resort: grab last {...}
                    m = re.search(r"\{.*\}\s*$", text, flags=re.S)
                    extracted = json.loads(m.group(0)) if m else {}

                # 3) Save PDF to MEDIA so the viewer can load it
                #    We'll put it under media/ocr/<original_name>
                save_path = f"ocr/{pdf_file.name}"
                stored_path = default_storage.save(save_path, ContentFile(pdf_bytes))
                # Build a URL clients can fetch (works in DEBUG with static serving configured)
                try:
                    pdf_url = default_storage.url(stored_path)
                except Exception:
                    pdf_url = (settings.MEDIA_URL.rstrip("/") + "/" + stored_path.lstrip("/"))


                # 4) Create a Document row carrying both the PDF URL and the parsed JSON
                doc = Document.objects.create(
                    source="pdf",
                    content_url=pdf_url,          # so the viewer can render it
                    payload_json=extracted,        # also keep the structured data
                    meta={"from": "gemini_2_5"},
                )

                # (Optional) Create a throwaway Patient so you can annotate immediately
                # or replace this with your real patient creation logic
                pat = Patient.objects.create(name="OCR Patient", external_id="OCR-ADHOC")

                result = {
                    "success": True,
                    "error": None,
                    "processing_time": dt,
                    # what the front-end needs to enable Start Annotating:
                    "document_id": doc.id,
                    "patient_id": pat.id,
                    "pdf_url": pdf_url,
                    # and the OCR JSON to display/edit:
                    "structured_data": extracted,
                    "raw_response": text,
                }
                return HttpResponse(json.dumps(result), content_type="application/json")

            except Exception as err:
                result = {
                    "success": False,
                    "error": str(err),
                    "processing_time": 0,
                    "structured_data": {},
                    "raw_response": "",
                }
                return HttpResponse(json.dumps(result), content_type="application/json", status=200)
        else:
            result = {
                "success": False,
                "error": "Missing PDF or API key",
                "processing_time": 0,
                "structured_data": {},
                "raw_response": "",
            }
            return HttpResponse(json.dumps(result), content_type="application/json", status=200)

    # GET -> show your uploader/test page
    return render(request, "ocr.html")



@csrf_exempt
def ocr_image(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST an image or PDF file with the 'file' key.")

    f = request.FILES.get("file")
    if not f:
        return HttpResponseBadRequest("No file uploaded under 'file'.")

    results = []
    if f.name.lower().endswith(".pdf"):
        try:
            pdf_bytes = f.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")  # type: ignore[arg-type]
        except Exception:
            return HttpResponseBadRequest("Invalid PDF.")
        for idx in range(doc.page_count):
            page = doc.load_page(idx)
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            arr = np.array(img)
            reader = get_reader(langs=["en", "id"], gpu=False)
            page_results = reader.readtext(arr, detail=1, paragraph=False)
            results.extend(page_results)
    else:
        try:
            img = Image.open(f).convert("RGB")
        except Exception:
            return HttpResponseBadRequest("Invalid image.")
        arr = np.array(img)
        reader = get_reader(langs=["en", "id"], gpu=False)
        results = reader.readtext(arr, detail=1, paragraph=False)

    payload = {"results": _normalize_results(results)}
    return HttpResponse(json.dumps(payload), content_type="application/json")


def _normalize_results(results):
    """(box, text, conf) -> dict with only plain Python types."""
    norm = []
    for box, text, conf in results:
        b = np.asarray(box, dtype=float).tolist()
        corrected = correct_word(str(text))
        norm.append({"box": b, "text": corrected, "confidence": float(conf)})
    return norm
