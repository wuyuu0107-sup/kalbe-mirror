# chat/service.py
import os
import re
import json
from typing import Optional, List

from django.conf import settings

from .repo import DB
from .sqlgen import build_sql
from .llm import get_intent_json, GeminiError, GeminiBlocked, ask_gemini_text
from .intent import parse_intent, Intent

# ======= Supabase Storage client (Opsi 2) =======
# pip install supabase
try:
    from supabase import create_client  # type: ignore
except Exception as _e:
    create_client = None  # biar jelas kalau lib belum diinstall

_SUPABASE_URL = os.getenv("SUPABASE_URL")
_SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
_SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "ocr")  # default bucket: ocr

_supabase = None
if create_client and _SUPABASE_URL and _SUPABASE_SERVICE_KEY:
    _supabase = create_client(_SUPABASE_URL, _SUPABASE_SERVICE_KEY)


# ============ INTENT RULES ============

def _rule_based_intent(nl: str) -> Intent:
    s = (nl or "").lower().strip()
    if not s:
        raise ValueError("Pertanyaan kosong.")

    # total pasien
    if ("total" in s and "pasien" in s) or ("semua" in s and "pasien" in s):
        return Intent(intent="TOTAL_PATIENTS", args={})

    # jumlah pasien per uji klinis <nama>
    if ("uji klinis" in s or "trial" in s) and ("berapa" in s or "jumlah" in s or "ada berapa" in s):
        m = re.search(r"(?:uji\s*klinis|trial)\s+([a-z0-9\-_/]+)", s)
        trial = m.group(1).upper() if m else None
        if trial:
            return Intent(intent="COUNT_PATIENTS_BY_TRIAL", args={"trial_name": trial})

    # ambil file JSON (titik/koma sebelum 'json' ditoleransi)
    m = re.search(r"(?:ambil(?:kan)?|fetch|get)\s+(?:saya\s+)?([a-z0-9_\-\/]+)\s*[,\.]\s*json", s)
    if m:
        fname = m.group(1)
        return Intent(intent="GET_FILE_BY_NAME", args={"filename": f"{fname}.json"})

    return Intent(intent="GENERAL_QUESTION", args={"text": s})


def _smart_intent(nl: str) -> Intent:
    try:
        return _rule_based_intent(nl)
    except Exception:
        pass

    use_gemini = getattr(settings, "USE_GEMINI", False) and getattr(settings, "GEMINI_API_KEY", None)
    if use_gemini:
        try:
            raw = get_intent_json(nl)
            return parse_intent(raw)
        except (GeminiBlocked, GeminiError):
            return Intent(intent="GENERAL_QUESTION", args={"text": nl.lower().strip()})

    return Intent(intent="GENERAL_QUESTION", args={"text": nl.lower().strip()})


# ============ DB HELPERS (untuk intent pasien) ============

def _fetch_scalar(sql, params=None):
    row = DB().fetch_one(sql, params or [])
    if row is None:
        return None
    return row[0] if isinstance(row, (tuple, list)) else next(iter(row.values()))


def _fetch_one(sql, params=None):
    return DB().fetch_one(sql, params or [])


# ============ Supabase Storage helpers ============

def _ensure_supabase():
    if _supabase is None:
        raise RuntimeError(
            "Supabase client belum tersedia. Pastikan SUPABASE_URL dan SUPABASE_SERVICE_KEY ter-set "
            "dan package 'supabase' sudah terinstall (pip install supabase)."
        )
    return _supabase


def _try_download(bucket: str, path: str) -> Optional[bytes]:
    sb = _ensure_supabase()
    try:
        data = sb.storage.from_(bucket).download(path)
        return data  # bytes
    except Exception:
        return None


def _list_paths(bucket: str, path: str = "") -> List[dict]:
    sb = _ensure_supabase()
    try:
        return sb.storage.from_(bucket).list(path=path or "")
    except Exception:
        return []


def _find_file_path(bucket: str, filename: str) -> Optional[str]:
    """
    Cari file di beberapa lokasi umum:
    1) filename (root)
    2) ocr/filename
    3) docs/filename
    4) scan root & level-1 folder lalu cocokin nama file
    """
    candidates = [
        filename,
        f"ocr/{filename}",
        f"docs/{filename}",
    ]

    for cand in candidates:
        if _try_download(bucket, cand):
            return cand  # ada dan bisa di-download

    # fallback: scan root
    root = _list_paths(bucket, "")
    # cek file di root
    for item in root:
        if not item.get("metadata"):  # folder biasanya punya metadata=None di SDK 2.x
            # Supabase SDK: item bisa folder/file; kita cek nama langsung
            if item.get("name") == filename:
                if _try_download(bucket, filename):
                    return filename

    # cek 1-level folder
    for item in root:
        # di SDK 2.x, folder ditandai "id" ada dan "name" string, metadata None → kita coba asumsikan folder
        if item.get("name") and item.get("id") and item.get("metadata") is None:
            folder = item["name"]
            sub = _list_paths(bucket, folder)
            for subitem in sub:
                if subitem.get("name") == filename:
                    cand = f"{folder}/{filename}"
                    if _try_download(bucket, cand):
                        return cand

    return None


def _get_json_from_storage(filename: str) -> str:
    """
    Download file JSON dari Supabase Storage bucket _SUPABASE_BUCKET.
    Return: pretty-printed JSON string atau pesan error yang ramah.
    """
    if not filename or not filename.endswith(".json"):
        return "Nama file tidak valid."

    path = _find_file_path(_SUPABASE_BUCKET, filename)
    if not path:
        return f"File '{filename}' tidak ditemukan di bucket '{_SUPABASE_BUCKET}'."

    raw = _try_download(_SUPABASE_BUCKET, path)
    if raw is None:
        return f"Gagal mengunduh '{path}' dari bucket '{_SUPABASE_BUCKET}'."

    try:
        text = raw.decode("utf-8")
    except Exception:
        return f"File '{path}' bukan UTF-8 atau rusak."

    try:
        data = json.loads(text)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception:
        # Kalau ternyata bukan JSON valid, kirim apa adanya
        return text


# ============ MAIN ENTRY ============

def answer_question(nl: str) -> str:
    intent = _smart_intent(nl)

    if intent.intent == "GENERAL_QUESTION":
        use_gemini = getattr(settings, "USE_GEMINI", False) and getattr(settings, "GEMINI_API_KEY", None)
        if use_gemini:
            try:
                return ask_gemini_text(nl)
            except (GeminiBlocked, GeminiError):
                pass
        return ("Aku bisa: (1) total pasien, (2) jumlah pasien per uji klinis, "
                "(3) ambil file JSON dari Supabase Storage, mis. 'ambilkan saya data_1.json'.")

    if intent.intent == "COUNT_PATIENTS_BY_TRIAL":
        trial = intent.args.get("trial_name")
        if not trial:
            return "Mohon sebutkan nama uji klinis yang dimaksud."

    if intent.intent == "GET_FILE_BY_NAME":
        filename = intent.args.get("filename")
        return _get_json_from_storage(filename)

    # intent via SQL (pasien)
    sql, params = build_sql(intent.intent, intent.args)

    if intent.intent in ("TOTAL_PATIENTS", "COUNT_PATIENTS_BY_TRIAL"):
        n = _fetch_scalar(sql, params)
        if intent.intent == "TOTAL_PATIENTS":
            return f"Total data pasien tersimpan: {n}."
        trial = intent.args.get("trial_name", "tertentu")
        return f"Jumlah pasien pada uji klinis {trial}: {n}."

    return "Maaf, aku belum bisa menjawab pertanyaan itu."