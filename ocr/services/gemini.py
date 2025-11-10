import time
import json
import re
from typing import Dict, Any
import google.generativeai as genai

class GeminiService:
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")
    
    def extract_medical_data(self, pdf_bytes: bytes) -> Dict[str, Any]:
        prompt = self._get_prompt()
        
        t0 = time.time()
        resp = self.model.generate_content(
            [prompt, {"mime_type": "application/pdf", "data": pdf_bytes}],
            generation_config={"temperature": 0},
        )
        dt = round(time.time() - t0, 2)
        
        text = self._clean_response_text(resp)
        parsed = self._parse_json(text)
        
        return {
            "parsed": parsed,
            "raw_text": text,
            "processing_time": dt
        }
    
    def _get_prompt(self) -> str:
        return """
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
    
    def _clean_response_text(self, resp) -> str:
        text = (getattr(resp, "text", "") or "").strip()
        text = re.sub(r"^```json\s*", "", text, flags=re.M)
        text = re.sub(r"^```\s*", "", text, flags=re.M)
        text = re.sub(r"\s*```$", "", text)
        return text
    
    def _parse_json(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except Exception:
            m = re.search(r"\{.*\}\s*$", text, flags=re.S)
            return json.loads(m.group(0)) if m else {}