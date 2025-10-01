import os
import re
import time
import json

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

import google.generativeai as genai
from dotenv import load_dotenv

# --- PDF support flag for tests / optional dependency --- jawa
try:
    import fitz  # PyMuPDF
    HAS_PDF = True
except ImportError:
    fitz = None  # type: ignore
    HAS_PDF = False



@csrf_exempt
def health(request):
    return JsonResponse({"status": "ok"}, status=200)


@csrf_exempt
def ocr_test_page(request):
    load_dotenv()
    if request.method == "POST":
        pdf_file = request.FILES.get("pdf")
        api_key = os.getenv("GEMINI_API_KEY")
        result: dict = {}
        if pdf_file and api_key:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-2.5-flash")
                prompt = """
                Analyze this medical document PDF and extract the following information in JSON format.
                If any information is not found, leave the value as null. for example, some of the data is in indonesian, like density in urinalysis, which is berat jenis in the pdf
                For urinalysis, hematology, and clinical chemistry, there is titles of the tables called "Hasil", "Nilai Rujukan", "Satuan", and "Metode", display them in the results in order like ""ph": 6.5, ..., ..., ...""
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
                   - ph : "Hasil", "Nilai Rujukan", "Satuan", "Metode"
                   - density
                   - glucose
                   - ketone
                   - urobilinogen
                   - bilirubin
                   - blood
                   - leucocyte_esterase
                   - nitrite
                6. HEMATOLOGY:
                   - hemoglobin : "Hasil", "Nilai Rujukan", "Satuan", "Metode"
                   - hematocrit
                   - leukocyte
                   - erythrocyte
                   - thrombocyte
                   - esr
                7. CLINICAL_CHEMISTRY:
                   - bilirubin_total : "Hasil", "Nilai Rujukan", "Satuan", "Metode"
                   - alkaline_phosphatase
                   - sgot
                   - sgpt
                   - ureum
                   - creatinine
                   - random_blood_glucose
                Provide ONLY the JSON object without any additional text or formatting.
                """.strip()

                pdf_data = pdf_file.read()
                start_time = time.time()
                response = model.generate_content(
                    [prompt, {"mime_type": "application/pdf", "data": pdf_data}]
                )
                processing_time = time.time() - start_time

                json_text = response.text.strip()
                json_text = re.sub(r"^```json\s*", "", json_text)
                json_text = re.sub(r"\s*```$", "", json_text)
                try:
                    extracted_data = json.loads(json_text)
                except Exception:
                    extracted_data = {}

                result = {
                    "structured_data": extracted_data,
                    "raw_response": json_text,
                    "processing_time": round(processing_time, 2),
                    "success": True,
                    "error": None,
                }
            except Exception as err:
                result = {
                    "error": str(err),
                    "structured_data": {},
                    "raw_response": "",
                    "processing_time": 0,
                    "success": False,
                }
        else:
            result = {
                "error": "Missing PDF or API key",
                "structured_data": {},
                "raw_response": "",
                "processing_time": 0,
                "success": False,
            }
        return HttpResponse(json.dumps(result), content_type="application/json")

    return render(request, "ocr.html")


