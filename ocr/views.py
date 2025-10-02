import os
import re
import time
import json

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
import os, time, json, re, mimetypes
from django.http import HttpResponse
from django.shortcuts import render
from dotenv import load_dotenv


# --- PDF support flag for tests / optional dependency ---
try:
    import fitz  # PyMuPDF
    HAS_PDF = True
except ImportError:
    fitz = None  # type: ignore
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

def order_sections(d: dict) -> dict:
    head = {k: d[k] for k in SECTION_ORDER if k in d}
    tail = {k: v for k, v in d.items() if k not in head}
    return {**head, **tail}

import re
from datetime import datetime

MEAS_KEYS = ("Hasil", "Nilai Rujukan", "Satuan", "Metode")

URINALYSIS_FIELDS = [
    "ph","density","glucose","ketone","urobilinogen",
    "bilirubin","blood","leucocyte_esterase","nitrite",
]
HEMATOLOGY_FIELDS = [
    "hemoglobin","hematocrit","leukocyte","erythrocyte","thrombocyte","esr",
]
CHEMISTRY_FIELDS = [
    "bilirubin_total","alkaline_phosphatase","sgot","sgpt","ureum","creatinine","random_blood_glucose",
]

def _meas_template():
    return {"Hasil": None, "Nilai Rujukan": None, "Satuan": None, "Metode": None}

def _to_str(x):
    if x is None:
        return None
    return str(x)

# Accept many common date formats, return DD/MMM/YYYY (MMM uppercase)
_DATE_FMTS = [
    "%d/%b/%Y", "%d-%b-%Y", "%d/%B/%Y", "%d-%B-%Y",
    "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y",
]
def _norm_date(s):
    if not s:
        return None
    if isinstance(s, (int, float)):
        s = str(s)
    s = s.strip()
    # already like 13/APR/2024?
    m = re.match(r"^\d{2}/[A-Za-z]{3}/\d{4}$", s)
    if m:
        # just uppercase month
        d, mon, y = s.split("/")
        return f"{d}/{mon[:3].upper()}/{y}"
    for fmt in _DATE_FMTS:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%d/%b/%Y").upper()
        except Exception:
            continue
    # last resort: keep original
    return s

def _serology_str(x):
    """Coerce serology value to a simple string."""
    if x is None:
        return None
    if isinstance(x, dict):
        # prefer 'Hasil' if present; otherwise any common key; fallback to str(x)
        for key in ("Hasil", "hasil", "value", "Value", "result", "Result"):
            if key in x and x[key] is not None:
                return str(x[key])
        return str(x)
    # scalar -> string
    return str(x)


def _as_meas(val, default_method=None):
    """
    Force the 4-key measurement object, with **strings** for values.
    """
    out = _meas_template()
    if isinstance(val, dict):
        for k in MEAS_KEYS:
            if k in val:
                out[k] = _to_str(val[k])
        # preserve any extra keys
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
    """
    Enforce your exact schema + types:
    - Measurement objects: 4 keys, values as **strings**
    - Dates: DD/MMM/YYYY (MMM uppercase)
    - DEMOGRAPHY: age=int if possible; weight/height/bmi as strings
    - VITAL_SIGNS: strings
    - SEROLOGY: strings
    - Final section order: DEMOGRAPHY, MEDICAL_HISTORY, VITAL_SIGNS, SEROLOGY, URINALYSIS, HEMATOLOGY, CLINICAL_CHEMISTRY, then extras
    """
    def _serology_str(x):
        if x is None:
            return None
        if isinstance(x, dict):
            for key in ("Hasil", "hasil", "value", "Value", "result", "Result"):
                if key in x and x[key] is not None:
                    return str(x[key])
            return str(x)
        return str(x)

    base = _default_payload()
    if not isinstance(extracted, dict):
        # return ordered empty schema
        return {
            "DEMOGRAPHY":          base["DEMOGRAPHY"],
            "MEDICAL_HISTORY":     base["MEDICAL_HISTORY"],
            "VITAL_SIGNS":         base["VITAL_SIGNS"],
            "SEROLOGY":            base["SEROLOGY"],
            "URINALYSIS":          base["URINALYSIS"],
            "HEMATOLOGY":          base["HEMATOLOGY"],
            "CLINICAL_CHEMISTRY":  base["CLINICAL_CHEMISTRY"],
        }

    # normalize top-level key names
    norm = {}
    for k, v in extracted.items():
        ku = k.upper().replace(" ", "_")
        mapping = {
            "DEMOGRAPHY":"DEMOGRAPHY",
            "MEDICAL_HISTORY":"MEDICAL_HISTORY",
            "VITAL_SIGNS":"VITAL_SIGNS",
            "SEROLOGY":"SEROLOGY",
            "URINALYSIS":"URINALYSIS",
            "HEMATOLOGY":"HEMATOLOGY",
            "CLINICAL_CHEMISTRY":"CLINICAL_CHEMISTRY",
        }
        norm[mapping.get(ku, k)] = v

    # merge simple dict sections
    for sec in ("DEMOGRAPHY", "MEDICAL_HISTORY", "VITAL_SIGNS"):
        if isinstance(norm.get(sec), dict):
            base[sec].update(norm[sec])

    # SEROLOGY should be strings
    if isinstance(norm.get("SEROLOGY"), dict):
        for k in base["SEROLOGY"].keys():
            base["SEROLOGY"][k] = _serology_str(norm["SEROLOGY"].get(k))

    # Measurement sections: merge then coerce to 4-key strings
    for sec, fields in (
        ("URINALYSIS", URINALYSIS_FIELDS),
        ("HEMATOLOGY", HEMATOLOGY_FIELDS),
        ("CLINICAL_CHEMISTRY", CHEMISTRY_FIELDS),
    ):
        if isinstance(norm.get(sec), dict):
            base[sec].update(norm[sec])
    _ensure_section(base["URINALYSIS"], URINALYSIS_FIELDS, default_method="Carik Celup")
    _ensure_section(base["HEMATOLOGY"], HEMATOLOGY_FIELDS)
    _ensure_section(base["CLINICAL_CHEMISTRY"], CHEMISTRY_FIELDS)

    # DEMOGRAPHY formatting
    d = base["DEMOGRAPHY"]
    d["screening_date"] = _norm_date(d.get("screening_date"))
    d["date_of_birth"]  = _norm_date(d.get("date_of_birth"))

    # age int if possible
    try:
        d["age"] = int(d["age"]) if d.get("age") not in (None, "") else None
    except Exception:
        d["age"] = None

    # weight/height/bmi as strings
    for k in ("weight_kg", "height_cm", "bmi"):
        if d.get(k) is not None:
            d[k] = _to_str(d[k])

    # vitals as strings
    v = base["VITAL_SIGNS"]
    for k in ("systolic_bp","diastolic_bp","heart_rate"):
        if v.get(k) is not None:
            v[k] = _to_str(v[k])

    # collect extras (unknown sections) to append at the end
    extras = {
        k: v for k, v in norm.items()
        if k not in ("DEMOGRAPHY","MEDICAL_HISTORY","VITAL_SIGNS","SEROLOGY","URINALYSIS","HEMATOLOGY","CLINICAL_CHEMISTRY")
    }

    # return in the exact order you want
    ordered = {
        "DEMOGRAPHY":          base["DEMOGRAPHY"],
        "MEDICAL_HISTORY":     base["MEDICAL_HISTORY"],
        "VITAL_SIGNS":         base["VITAL_SIGNS"],
        "SEROLOGY":            base["SEROLOGY"],
        "URINALYSIS":          base["URINALYSIS"],
        "HEMATOLOGY":          base["HEMATOLOGY"],
        "CLINICAL_CHEMISTRY":  base["CLINICAL_CHEMISTRY"],
    }
    ordered.update(extras)
    return ordered

@csrf_exempt
def health(request):
    return JsonResponse({"status": "ok"}, status=200)




@csrf_exempt
def ocr_test_page(request):
    load_dotenv()  # loads SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, GEMINI_API_KEY, etc.

    if request.method == "POST":
        pdf_file = request.FILES.get("pdf")
        api_key = os.getenv("GEMINI_API_KEY")
        result: dict = {}

        if pdf_file and api_key:
            try:
                # 0) Supabase client (for Storage uploads)
                SUPABASE_URL = os.getenv("SUPABASE_URL")
                SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # server-side only!
                SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "ocr")

                supabase: Client | None = None
                if SUPABASE_URL and SUPABASE_KEY:
                    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

                # 1) OCR with Gemini
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

                # 2) Clean + parse JSON (strip code fences if present)
                text = (getattr(resp, "text", "") or "").strip()
                text = re.sub(r"^```json\s*", "", text, flags=re.M)
                text = re.sub(r"^```\s*", "", text, flags=re.M)
                text = re.sub(r"\s*```$", "", text)

                try:
                    extracted = json.loads(text)
                except Exception:
                    m = re.search(r"\{.*\}\s*$", text, flags=re.S)
                    extracted = json.loads(m.group(0)) if m else {}

                # Always normalize + order
                extracted = normalize_payload(extracted)
                ordered = order_sections(extracted)

                # 3) Save PDF locally (optional dev fallback)
                local_save_path = f"ocr/{pdf_file.name}"
                stored_path = default_storage.save(local_save_path, ContentFile(pdf_bytes))
                try:
                    local_pdf_url = default_storage.url(stored_path)
                except Exception:
                    local_pdf_url = (settings.MEDIA_URL.rstrip("/") + "/" + stored_path.lstrip("/"))

                # 4) Upload to Supabase Storage (preferred for prod)
                supabase_pdf_url = None
                supabase_json_url = None
                if supabase:
                    ts = int(time.time())
                    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", pdf_file.name)
                    storage_path = f"{ts}_{safe_name}"  # path INSIDE the bucket

                    content_type = mimetypes.guess_type(pdf_file.name)[0] or "application/pdf"
                    file_opts = {"contentType": content_type, "upsert": "true"}

                    storage = supabase.storage.from_(SUPABASE_BUCKET)

                    # Upload PDF
                    _ = storage.upload(path=storage_path, file=pdf_bytes, file_options=file_opts)

                    # Helper to normalize SDK return types (str / dict)
                    def _to_url(val):
                        if isinstance(val, str):
                            return val
                        if isinstance(val, dict):
                            return val.get("publicURL") or val.get("public_url") or val.get("signedURL") or val.get("signed_url")
                        return None

                    # Public or signed URL for PDF
                    try:
                        pub = storage.get_public_url(storage_path)
                        supabase_pdf_url = _to_url(pub)
                    except Exception:
                        supabase_pdf_url = None
                    if not supabase_pdf_url:
                        signed = storage.create_signed_url(storage_path, 7 * 24 * 3600)
                        supabase_pdf_url = _to_url(signed)
                    if supabase_pdf_url:
                        supabase_pdf_url = supabase_pdf_url.rstrip("?")

                    # (B) Upload OCR JSON as a sidecar file (use ordered!)
                    json_bytes = json.dumps(
                        ordered,  # <-- ordered
                        ensure_ascii=False, separators=(",", ":"), indent=2
                    ).encode("utf-8")
                    json_path = storage_path.rsplit(".", 1)[0] + ".json"
                    json_opts = {"contentType": "application/json", "upsert": "true"}

                    _ = storage.upload(path=json_path, file=json_bytes, file_options=json_opts)

                    # Public or signed URL for JSON
                    try:
                        pub_json = storage.get_public_url(json_path)
                        supabase_json_url = _to_url(pub_json)
                    except Exception:
                        supabase_json_url = None
                    if not supabase_json_url:
                        signed_json = storage.create_signed_url(json_path, 7 * 24 * 3600)
                        supabase_json_url = _to_url(signed_json)
                    if supabase_json_url:
                        supabase_json_url = supabase_json_url.rstrip("?")

                # Prefer Supabase PDF URL; keep local as a fallback in meta
                final_pdf_url = supabase_pdf_url or local_pdf_url

                # 5) Create DB rows (writes to Supabase Postgres via your DATABASE_URL)
                doc = Document.objects.create(
                    source="pdf",
                    content_url=final_pdf_url,
                    payload_json=ordered,  # <-- ordered
                    meta={
                        "from": "gemini_2_5",
                        "local_fallback_url": local_pdf_url,
                        "storage_pdf_url": supabase_pdf_url,
                        "storage_json_url": supabase_json_url,
                        "section_order": [
                            "DEMOGRAPHY","MEDICAL_HISTORY","VITAL_SIGNS",
                            "SEROLOGY","URINALYSIS","HEMATOLOGY","CLINICAL_CHEMISTRY"
                        ],
                    },
                )
                pat = Patient.objects.create(name="OCR Patient", external_id="OCR-ADHOC")
                print("STRUCTURED_DATA_KEYS_ORDER:", list(ordered.keys()))

                result = {
                    "success": True,
                    "error": None,
                    "processing_time": dt,
                    "document_id": doc.id,
                    "patient_id": pat.id,
                    "pdf_url": final_pdf_url,
                    "structured_data": ordered,   # <-- ordered
                    "raw_response": text,
                    "storage_json_url": supabase_json_url,
                }

                # Optional debug: confirm order in server logs
                # print("STRUCTURED_DATA_KEYS_ORDER:", list(ordered.keys()))

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


