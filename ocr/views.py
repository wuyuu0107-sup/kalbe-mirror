import google.generativeai as genai
import re
import time
import os
import tempfile
import fitz  
import json
import numpy as np
from PIL import Image
from django.http import HttpResponseBadRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from .reader import get_reader
from .utils import correct_word
from dotenv import load_dotenv

@csrf_exempt
def ocr_test_page(request):
    load_dotenv()
    if request.method == "POST":
        pdf_file = request.FILES.get("pdf")
        api_key = os.getenv("GEMINI_API_KEY")
        result = {}
        if pdf_file and api_key:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                prompt = """
                Analyze this medical document PDF and extract the following information in JSON format.
                If any information is not found, leave the value as null.
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
                Provide ONLY the JSON object without any additional text or formatting.
                """
                pdf_data = pdf_file.read()
                start_time = time.time()
                response = model.generate_content([
                    prompt,
                    {'mime_type': 'application/pdf', 'data': pdf_data}
                ])
                processing_time = time.time() - start_time
                json_text = response.text.strip()
                json_text = re.sub(r'^```json\s*', '', json_text)
                json_text = re.sub(r'\s*```$', '', json_text)
                try:
                    extracted_data = json.loads(json_text)
                except Exception as e:
                    extracted_data = {}
                result = {
                    'structured_data': extracted_data,
                    'raw_response': json_text,
                    'processing_time': round(processing_time, 2),
                    'success': True,
                    'error': None
                }
            except Exception as e:
                result = {
                    'error': str(e),
                    'structured_data': {},
                    'raw_response': '',
                    'processing_time': 0,
                    'success': False
                }
        else:
            result = {
                'error': 'Missing PDF or API key',
                'structured_data': {},
                'raw_response': '',
                'processing_time': 0,
                'success': False
            }
        return HttpResponse(json.dumps(result), content_type='application/json')
    return render(request, "ocr.html")

@csrf_exempt
def ocr_image(request):
    if request.method != "POST":
        return HttpResponseBadRequest("POST an image or PDF file with the 'file' key.")

    f = request.FILES.get("file")
    if not f:
        return HttpResponseBadRequest("No file uploaded under 'file'.")

    results = []
    if f.name.lower().endswith('.pdf'):
        try:
            pdf_bytes = f.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
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
        except Exception as e:
            return HttpResponseBadRequest("Invalid image.")
        arr = np.array(img)
        reader = get_reader(langs=["en", "id"], gpu=False)
        results = reader.readtext(arr, detail=1, paragraph=False)

    payload = {"results": _normalize_results(results)}
    return HttpResponse(json.dumps(payload), content_type='application/json')


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
