from typing import Dict, Any, Optional, Tuple, List
import os
import re
import time
import json
from datetime import datetime
from dashboard.tracking import track_feature
import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
import google.generativeai as genai
from dotenv import load_dotenv

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings

from annotation.models import Document, Patient
from supabase import create_client, Client
import mimetypes

logger = logging.getLogger(__name__)

try:
    import fitz
    HAS_PDF = True
except ImportError:
    fitz = None
    HAS_PDF = False

SECTION_ORDER = [
    "DEMOGRAPHY",
    "MEDICAL_HISTORY",
    "VITAL_SIGNS",
    "SEROLOGY",
    "URINALYSIS",
    "HEMATOLOGY",
    "CLINICAL_CHEMISTRY",
]

MEAS_KEYS = ("Hasil", "Nilai Rujukan", "Satuan", "Metode")

URINALYSIS_FIELDS = [
    "ph", "density", "glucose", "ketone", "urobilinogen",
    "bilirubin", "blood", "leucocyte_esterase", "nitrite",
]
HEMATOLOGY_FIELDS = [
    "hemoglobin", "hematocrit", "leukocyte", "erythrocyte", "thrombocyte", "esr",
]
CHEMISTRY_FIELDS = [
    "bilirubin_total", "alkaline_phosphatase", "sgot", "sgpt", "ureum", "creatinine", "random_blood_glucose",
]

_DATE_FMTS = [
    "%d/%b/%Y", "%d-%b-%Y", "%d/%B/%Y", "%d-%B-%Y",
    "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y",
]


def order_sections(d: dict) -> dict:
    head = {k: d[k] for k in SECTION_ORDER if k in d}
    tail = {k: v for k, v in d.items() if k not in head}
    return {**head, **tail}


def _meas_template():
    return {"Hasil": None, "Nilai Rujukan": None, "Satuan": None, "Metode": None}


def _to_str(x):
    if x is None:
        return None
    return str(x)


def _norm_date(s):
    
    if not s:
        return None
    if isinstance(s, (int, float)):
        s = str(s)
    s = s.strip()
    
    m = re.match(r"^\d{2}/[A-Za-z]{3}/\d{4}$", s)
    if m:
        d, mon, y = s.split("/")
        return f"{d}/{mon[:3].upper()}/{y}"
    
    for fmt in _DATE_FMTS:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%d/%b/%Y").upper()
        except Exception:
            continue
    
    return s


def _as_meas(val, default_method=None):

    out = _meas_template()
    if isinstance(val, dict):
        for k in MEAS_KEYS:
            if k in val:
                out[k] = _to_str(val[k])
        for k, v in val.items():
            if k not in out:
                out[k] = v
    elif val is not None:
        out["Hasil"] = _to_str(val)
    if default_method and not out.get("Metode"):
        out["Metode"] = default_method
    return out

def _ensure_section(obj, fields, default_method=None):

    for f in fields:
        val = obj.get(f) if isinstance(obj, dict) else None
        obj[f] = _as_meas(val, default_method=default_method)

def _default_payload():

    return {
        "DEMOGRAPHY": {
            "subject_initials": None, "sin": None, "study_drug": None,
            "screening_date": None, "gender": None, "date_of_birth": None,
            "age": None, "weight_kg": None, "height_cm": None, "bmi": None,
        },
        "MEDICAL_HISTORY": {"smoker_cigarettes_per_day": None},
        "VITAL_SIGNS": {"systolic_bp": None, "diastolic_bp": None, "heart_rate": None},
        "SEROLOGY": {"hbsag": None, "hcv": None, "hiv": None},
        "URINALYSIS": {k: _meas_template() for k in URINALYSIS_FIELDS},
        "HEMATOLOGY": {k: _meas_template() for k in HEMATOLOGY_FIELDS},
        "CLINICAL_CHEMISTRY": {k: _meas_template() for k in CHEMISTRY_FIELDS},
    }

def normalize_payload(extracted: dict) -> dict:

    base = _default_payload()
    
    if not isinstance(extracted, dict):
        return _build_ordered_output(base, {})
    
    norm = _normalize_section_keys(extracted)
    _merge_simple_sections(norm, base)
    _process_serology(norm.get("SEROLOGY", {}), base["SEROLOGY"])
    _process_measurement_sections(norm, base)
    _process_demography(base["DEMOGRAPHY"])
    _process_vital_signs(base["VITAL_SIGNS"])
    
    extras = _collect_extra_sections(norm)
    return _build_ordered_output(base, extras)


def _normalize_section_keys(extracted: Dict[str, Any]) -> Dict[str, Any]:

    norm = {}
    mapping = {
        "DEMOGRAPHY": "DEMOGRAPHY",
        "MEDICAL_HISTORY": "MEDICAL_HISTORY",
        "VITAL_SIGNS": "VITAL_SIGNS",
        "SEROLOGY": "SEROLOGY",
        "URINALYSIS": "URINALYSIS",
        "HEMATOLOGY": "HEMATOLOGY",
        "CLINICAL_CHEMISTRY": "CLINICAL_CHEMISTRY",
    }
    
    for k, v in extracted.items():
        ku = k.upper().replace(" ", "_")
        norm[mapping.get(ku, k)] = v
    
    return norm

def _merge_simple_sections(norm: Dict[str, Any], base: Dict[str, Any]) -> None:

    for sec in ("DEMOGRAPHY", "MEDICAL_HISTORY", "VITAL_SIGNS"):
        if isinstance(norm.get(sec), dict):
            base[sec].update(norm[sec])

def _process_demography(demo: Dict[str, Any]) -> None:

    demo["screening_date"] = _norm_date(demo.get("screening_date"))
    demo["date_of_birth"] = _norm_date(demo.get("date_of_birth"))
    
    demo["age"] = _convert_age_to_int(demo.get("age"))
    
    for k in ("weight_kg", "height_cm", "bmi"):
        if demo.get(k) is not None:
            demo[k] = _to_str(demo[k])

def _convert_age_to_int(age_value) -> Optional[int]:
    try:
        return int(age_value) if age_value not in (None, "") else None
    except Exception:
        return None

def _process_vital_signs(vitals: Dict[str, Any]) -> None:

    for k in ("systolic_bp", "diastolic_bp", "heart_rate"):
        if vitals.get(k) is not None:
            vitals[k] = _to_str(vitals[k])

def _process_serology(serology: Dict[str, Any], base: Dict[str, Any]) -> None:
    if not isinstance(serology, dict):
        return
    
    for k in base.keys():
        base[k] = _serology_str(serology.get(k))

def _serology_str(x):

    if x is None:
        return None
    if isinstance(x, dict):
        for key in ("Hasil", "hasil", "value", "Value", "result", "Result"):
            if key in x and x[key] is not None:
                return str(x[key])
        return str(x)
    return str(x)

def _process_measurement_sections(norm: Dict[str, Any], base: Dict[str, Any]) -> None:

    sections = [
        ("URINALYSIS", URINALYSIS_FIELDS, "Carik Celup"),
        ("HEMATOLOGY", HEMATOLOGY_FIELDS, None),
        ("CLINICAL_CHEMISTRY", CHEMISTRY_FIELDS, None),
    ]
    
    for sec, fields, default_method in sections:
        if isinstance(norm.get(sec), dict):
            base[sec].update(norm[sec])
        _ensure_section(base[sec], fields, default_method=default_method)


def _collect_extra_sections(norm: Dict[str, Any]) -> Dict[str, Any]:

    known_sections = {
        "DEMOGRAPHY", "MEDICAL_HISTORY", "VITAL_SIGNS",
        "SEROLOGY", "URINALYSIS", "HEMATOLOGY", "CLINICAL_CHEMISTRY"
    }
    return {k: v for k, v in norm.items() if k not in known_sections}


def _build_ordered_output(base: Dict[str, Any], extras: Dict[str, Any]) -> Dict[str, Any]:

    ordered = {
        "DEMOGRAPHY": base["DEMOGRAPHY"],
        "MEDICAL_HISTORY": base["MEDICAL_HISTORY"],
        "VITAL_SIGNS": base["VITAL_SIGNS"],
        "SEROLOGY": base["SEROLOGY"],
        "URINALYSIS": base["URINALYSIS"],
        "HEMATOLOGY": base["HEMATOLOGY"],
        "CLINICAL_CHEMISTRY": base["CLINICAL_CHEMISTRY"],
    }
    ordered.update(extras)
    return ordered


@csrf_exempt
def health(request):
    return JsonResponse({"status": "ok"}, status=200)


@csrf_exempt
@track_feature("ocr")
def ocr_test_page(request):
    load_dotenv()

    if request.method == "POST":
        pdf_file = request.FILES.get("pdf")
        api_key = os.getenv("GEMINI_API_KEY")
        result: dict = {}

        if pdf_file and api_key:
            try:
                supabase_client = _create_supabase_client()
                
                pdf_bytes = pdf_file.read()
                extracted_data = _extract_data_from_pdf(pdf_bytes, api_key)
                
                normalized_data = normalize_payload(extracted_data["parsed"])
                ordered_data = order_sections(normalized_data)
                
                local_pdf_url = _save_pdf_locally(pdf_file.name, pdf_bytes)
                supabase_urls = _upload_to_supabase(
                    supabase_client, pdf_file.name, pdf_bytes, ordered_data
                )
                
                document, patient = _create_database_records(
                    ordered_data, supabase_urls, local_pdf_url
                )
                
                result = _build_success_response(
                    document, patient, ordered_data, extracted_data, supabase_urls
                )
                
                return HttpResponse(json.dumps(result), content_type="application/json")

            except Exception as err:
                return _build_error_response(str(err))
        else:
            return _build_error_response("Missing PDF or API key")
    
    return render(request, "ocr.html")


def _create_supabase_client() -> Optional[Client]:

    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if SUPABASE_URL and SUPABASE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None


def _extract_data_from_pdf(pdf_bytes: bytes, api_key: str) -> Dict[str, Any]:
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

    t0 = time.time()
    resp = model.generate_content(
        [prompt, {"mime_type": "application/pdf", "data": pdf_bytes}],
        generation_config={"temperature": 0},
    )
    dt = round(time.time() - t0, 2)

    text = (getattr(resp, "text", "") or "").strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.M)
    text = re.sub(r"^```\s*", "", text, flags=re.M)
    text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}\s*$", text, flags=re.S)
        parsed = json.loads(m.group(0)) if m else {}

    return {
        "parsed": parsed,
        "raw_text": text,
        "processing_time": dt
    }

def _save_pdf_locally(filename: str, pdf_bytes: bytes) -> str:

    local_save_path = f"ocr/{filename}"
    stored_path = default_storage.save(local_save_path, ContentFile(pdf_bytes))
    
    try:
        return default_storage.url(stored_path)
    except Exception:
        return (settings.MEDIA_URL.rstrip("/") + "/" + stored_path.lstrip("/"))
    

def _upload_to_supabase(
        
    supabase: Optional[Client],
    filename: str,
    pdf_bytes: bytes,
    ordered_data: Dict[str, Any]

) -> Dict[str, Optional[str]]:
    if not supabase:
        return {"pdf_url": None, "json_url": None}
    
    SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "ocr")
    storage = supabase.storage.from_(SUPABASE_BUCKET)
    
    ts = int(time.time())
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", filename)
    storage_path = f"{ts}_{safe_name}"
    
    pdf_url = _upload_pdf_to_storage(storage, storage_path, pdf_bytes, filename)
    json_url = _upload_json_to_storage(storage, storage_path, ordered_data)
    
    return {"pdf_url": pdf_url, "json_url": json_url}


def _upload_pdf_to_storage(storage, storage_path: str, pdf_bytes: bytes, filename: str) -> Optional[str]:

    content_type = mimetypes.guess_type(filename)[0] or "application/pdf"
    file_opts = {"contentType": content_type, "upsert": "true"}
    
    storage.upload(path=storage_path, file=pdf_bytes, file_options=file_opts)
    
    try:
        signed_res = storage.create_signed_url(storage_path, 60 * 60)
        return _extract_url_from_response(signed_res)
    except Exception as e:
        logger.warning("Failed to create signed URL for %s: %s", storage_path, e)
        return None


def _upload_json_to_storage(storage, storage_path: str, ordered_data: Dict[str, Any]) -> Optional[str]:

    json_bytes = json.dumps(
        ordered_data,
        ensure_ascii=False,
        separators=(",", ":"),
        indent=2
    ).encode("utf-8")
    
    json_path = storage_path.rsplit(".", 1)[0] + ".json"
    json_opts = {"contentType": "application/json", "upsert": "true"}
    
    storage.upload(path=json_path, file=json_bytes, file_options=json_opts)
    
    try:
        pub_json = storage.get_public_url(json_path)
        return _extract_url_from_response(pub_json)
    except Exception:
        try:
            signed_json = storage.create_signed_url(json_path, 7 * 24 * 3600)
            return _extract_url_from_response(signed_json)
        except Exception:
            return None


def _extract_url_from_response(val) -> Optional[str]:

    if isinstance(val, str):
        return val.rstrip("?")
    if isinstance(val, dict):
        url = (
            val.get("signedURL")
            or val.get("signed_url")
            or val.get("publicURL")
            or val.get("public_url")
            or val.get("url")
        )
        return url.rstrip("?") if url else None
    return None


def _create_database_records(
        
    ordered_data: Dict[str, Any],
    supabase_urls: Dict[str, Optional[str]],
    local_pdf_url: str

) -> Tuple[Document, Patient]:
    final_pdf_url = supabase_urls["pdf_url"] or local_pdf_url
    
    doc = Document.objects.create(
        source="pdf",
        content_url=final_pdf_url,
        payload_json=ordered_data,
        meta={
            "from": "gemini_2_5",
            "local_fallback_url": local_pdf_url,
            "storage_pdf_url": supabase_urls["pdf_url"],
            "storage_json_url": supabase_urls["json_url"],
            "section_order": SECTION_ORDER,
        },
    )
    
    pat = Patient.objects.create(name="OCR Patient", external_id="OCR-ADHOC")
    
    return doc, pat


def _build_success_response(
        
    document: Document,
    patient: Patient,
    ordered_data: Dict[str, Any],
    extracted_data: Dict[str, Any],
    supabase_urls: Dict[str, Optional[str]]

) -> Dict[str, Any]:
    return {
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


def _build_error_response(error_message: str) -> HttpResponse:
    result = {
        "success": False,
        "error": error_message,
        "processing_time": 0,
        "structured_data": {},
        "raw_response": "",
    }
    return HttpResponse(json.dumps(result), content_type="application/json", status=200)