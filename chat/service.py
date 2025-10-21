# chat/service.py
import os
import re
import json
from typing import Optional, List
import logging

from django.conf import settings

from .repo import DB
from .sqlgen import build_sql
from .llm import get_intent_json, GeminiError, GeminiBlocked, ask_gemini_text
from .intent import parse_intent, Intent

logger = logging.getLogger(__name__)

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

# ========== DEBUG BUCKET ========
import base64, json as _json, re as _re
from urllib.parse import urlparse

def _jwt_role(api_key: str) -> str | None:
    # Supabase keys = JWT. Ambil payload (bagian tengah) dan baca claim 'role'
    try:
        parts = (api_key or "").split(".")
        if len(parts) < 2:
            return None
        pad = '=' * (-len(parts[1]) % 4)
        payload = base64.urlsafe_b64decode(parts[1] + pad)
        data = _json.loads(payload.decode("utf-8"))
        return data.get("role") or data.get("app_metadata", {}).get("role")
    except Exception:
        return None

def _project_ref_from_url(url: str) -> str | None:
    try:
        host = urlparse(url or "").netloc
        # typical host: abcdefghijklmnop.supabase.co  -> project ref = abcdefghijklmnop
        m = _re.match(r"^([a-z0-9]{20})\.supabase\.co$", host)
        return m.group(1) if m else host
    except Exception:
        return None


# ============ INTENT RULES ============
def _rule_based_intent(nl: str) -> Intent:
    s = (nl or "").lower().strip()
    if not s:
        raise ValueError("Pertanyaan kosong.")

    # whoami (supabase)
    if "whoami" in s and "supabase" in s:
        return Intent(intent="SUPABASE_WHOAMI", args={})

    # list buckets
    if "list" in s and "buckets" in s:
        return Intent(intent="LIST_BUCKETS", args={})

    # list/print files in storage
    if re.search(r"\b(list|daftar|tampilkan|print|show)\b.*\b(file|files|berkas|objek|object)\b", s) or \
       "list files" in s or "list storage" in s:
        # optional prefix, e.g., "list files in ocr/" or "list files ocr/"
        m = re.search(r"(?:in|di)\s+([a-z0-9_\-/]+)", s)
        prefix = m.group(1).strip() if m else ""
        return Intent(intent="LIST_STORAGE_FILES", args={"prefix": prefix})

    # auth user count
    if re.search(r"\b(berapa|jumlah|total|ada\s*berapa)\b.*\b(user|pengguna|akun)\b", s) or \
       "auth user" in s or "auth_user" in s:
        is_active_only = bool(re.search(r"\baktif|active\b", s))
        return Intent(intent="COUNT_AUTH_USERS", args={"active_only": is_active_only})

    # total pasien (more permissive)
    if re.search(r"\b(berapa|jumlah|total|ada\s*berapa)\b.*\b(pasien|data\s*pasien|database)\b", s):
        return Intent(intent="TOTAL_PATIENTS", args={})

    # jumlah pasien per uji klinis/trial <nama>
    if re.search(r"\b(uji\s*klinis|trial)\b", s) and re.search(r"\b(berapa|jumlah|ada\s*berapa)\b", s):
        # accept: "uji klinis ABC", "trial abc-123", etc. Also support quotes.
        m = re.search(r"(?:uji\s*klinis|trial)\s+([a-z0-9\-_\/]+|\"[^\"]+\"|'[^']+')", s)
        trial = None
        if m:
            trial_raw = m.group(1).strip().strip('"').strip("'")
            if trial_raw:
                trial = trial_raw.upper()
        return Intent(intent="COUNT_PATIENTS_BY_TRIAL", args={"trial_name": trial})

    # ambil file JSON (accept both "ambil data_1.json" and "ambil data_1, json")
    m = re.search(r"(?:ambil(?:kan)?|fetch|get)\s+(?:saya\s+)?([a-z0-9_\-\/]+)(?:\s*[,\.]\s*json|\s*\.json)\b", s)
    if m:
        fname = m.group(1)
        return Intent(intent="GET_FILE_BY_NAME", args={"filename": f"{fname}.json" if not fname.endswith(".json") else fname})

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


# ============ DB HELPERS ============
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
            "Supabase client belum tersedia. Pastikan SUPABASE_URL & SUPABASE_SERVICE_KEY ter-set "
            "dan package 'supabase' sudah terinstall (pip install supabase)."
        )
    return _supabase


def _coerce_download_result(res) -> Optional[bytes]:
    # Handle common shapes: bytes, dict{'data': bytes}, Response-like, or objects with .read()
    try:
        if isinstance(res, (bytes, bytearray)):
            return bytes(res)
        if isinstance(res, dict) and res.get("data") is not None:
            data = res["data"]
            return bytes(data) if isinstance(data, (bytes, bytearray)) else None
        if hasattr(res, "read"):
            return res.read()
        for attr in ("content", "raw", "body"):
            v = getattr(res, attr, None)
            if isinstance(v, (bytes, bytearray)):
                return bytes(v)
    except Exception as e:
        logger.debug("download result coercion failed: %s", e)
    return None


def _try_download(bucket: str, path: str) -> Optional[bytes]:
    sb = _ensure_supabase()
    try:
        res = sb.storage.from_(bucket).download(path)
        data = _coerce_download_result(res)
        if data is None:
            logger.debug("Supabase download returned unexpected type for %s/%s: %r", bucket, path, type(res))
        return data
    except Exception as e:
        logger.debug("Supabase download failed for %s/%s: %s", bucket, path, e)
        return None


def _list_paths(bucket: str, path: str = "") -> List[dict]:
    """
    Normalize .list() differences across SDK versions:
    - some use list(path=...), some list(path) positional, some list(prefix=...), etc.
    """
    sb = _ensure_supabase()
    candidates = [
        {"kw": {"path": path or ""}, "pos": None},
        {"kw": {"prefix": path or ""}, "pos": None},
        {"kw": {}, "pos": (path or "",)},
        {"kw": {"path": path or "", "limit": 1000}, "pos": None},
    ]
    for cand in candidates:
        try:
            res = sb.storage.from_(bucket).list(*(cand["pos"] or ()), **cand["kw"])
            if isinstance(res, list):
                return res
            if isinstance(res, dict) and "data" in res:
                return res.get("data") or []
            if hasattr(res, "get"):
                data = res.get("data")
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.debug("Supabase list variant failed (%s): %s", cand, e)
    logger.debug("Supabase list failed for %s/%s using all variants.", bucket, path)
    return []


def _find_file_path(bucket: str, filename: str) -> Optional[str]:
    candidates = [
        filename,
        f"ocr/{filename}",
        f"ocr/ocr/{filename}",
        f"docs/{filename}",
        f"public/{filename}",
    ]
    tried = []
    seen = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        tried.append(cand)
        if _try_download(bucket, cand):
            logger.debug("Storage: found file at candidate path: %s", cand)
            return cand

    # BFS scan folders
    to_visit = [""]
    visited = set()
    max_iters = 2000
    iters = 0

    while to_visit and iters < max_iters:
        iters += 1
        prefix = to_visit.pop(0)
        if prefix in visited:
            continue
        visited.add(prefix)

        items = _list_paths(bucket, prefix or "")
        for item in items:
            name = item.get("name") if isinstance(item, dict) else (item if isinstance(item, str) else None)
            if not name:
                continue

            # Heuristic: entries with no 'metadata' or with 'id' only might be folders in some SDKs
            is_folder = False
            if isinstance(item, dict):
                t = (item.get("type") or item.get("kind") or "").lower()
                size = item.get("size", None)
                if t in ("folder", "directory"):
                    is_folder = True
                elif size is None and not name.lower().endswith(".json"):
                    # Best-effort: many SDKs omit 'size' for folders
                    is_folder = True

            path = f"{prefix}/{name}" if prefix else name
            if is_folder:
                if path not in visited:
                    to_visit.append(path)
                continue

            # File candidate
            if name == filename or path.endswith("/" + filename) or path.endswith(filename):
                tried.append(path)
                if _try_download(bucket, path):
                    logger.debug("Storage: found file at scanned path: %s", path)
                    return path

    logger.debug("Storage: file not found. bucket=%s filename=%s tried=%s", bucket, filename, tried)
    return None


def _get_json_from_storage(filename: str) -> str:
    """
    Download file JSON dari Supabase Storage bucket _SUPABASE_BUCKET.
    Return: pretty-printed JSON string atau pesan error yang ramah.
    """
    if not filename or not filename.endswith(".json"):
        return "Nama file tidak valid."

    bucket = _SUPABASE_BUCKET
    try:
        path = _find_file_path(bucket, filename)
        if not path:
            logger.info("Storage: %s not found in bucket %s", filename, bucket)
            return f"File '{filename}' tidak ditemukan di bucket '{bucket}'."

        raw = _try_download(bucket, path)
        if raw is None:
            logger.warning("Storage: failed downloading %s from bucket %s", path, bucket)
            return f"Gagal mengunduh '{path}' dari bucket '{bucket}'."

        try:
            text = raw.decode("utf-8")
        except Exception:
            return f"File '{path}' bukan UTF-8 atau rusak."

        try:
            data = json.loads(text)
            return json.dumps(data, ensure_ascii=False, indent=2)
        except Exception:
            # Not valid JSON; return as-is
            return text
    except RuntimeError as e:
        logger.error("Storage: misconfiguration - %s", e)
        return str(e)
    except Exception as e:
        logger.exception("Storage: unexpected error fetching %s", filename)
        return f"Terjadi kesalahan saat mengambil '{filename}': {e}"


# ============ MAIN ENTRY ============
def answer_question(nl: str) -> str:
    intent = _smart_intent(nl)
    logger.info("SUPABASE_URL=%s ; SUPABASE_BUCKET=%s", _SUPABASE_URL, _SUPABASE_BUCKET)
    logger.debug("Intent resolved: %s %s", intent.intent, intent.args)

    # List buckets
    if intent.intent == "LIST_BUCKETS":
        try:
            sb = _ensure_supabase()
            if hasattr(sb.storage, "list_buckets"):
                bs = sb.storage.list_buckets() or []
                names = [b.get("name") for b in bs if isinstance(b, dict)]
                return "Buckets: " + (", ".join(names) if names else "(kosong)")
            return "SDK tidak mendukung list_buckets di versi ini."
        except Exception as e:
            logger.exception("list_buckets failed")
            return f"Gagal membaca daftar buckets: {e}"

    # whoami
    if intent.intent == "SUPABASE_WHOAMI":
        try:
            url = os.getenv("SUPABASE_URL") or ""
            key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY") or ""
            bucket = _SUPABASE_BUCKET
            role = _jwt_role(key) or "unknown"
            pref = _project_ref_from_url(url) or "unknown"

            # list buckets (but ok if not supported)
            sb = _ensure_supabase()
            buckets = []
            try:
                if hasattr(sb.storage, "list_buckets"):
                    buckets = [b.get("name") for b in sb.storage.list_buckets() or []]
            except Exception:
                pass

            return (
                f"Supabase URL host/project: {pref}\n"
                f"Key role: {role}\n"
                f"Configured bucket: {bucket}\n"
                f"Buckets visible: {', '.join(buckets) if buckets else '(tidak bisa dibaca)'}"
            )
        except Exception as e:
            return f"WHOAMI error: {e}"

    # list storage files
    if intent.intent == "LIST_STORAGE_FILES":
        prefix = (intent.args.get("prefix") or "").strip().strip("/")
        try:
            keys = _list_all_objects(_SUPABASE_BUCKET, prefix)
            if not keys:
                where = f" di '{prefix}/'" if prefix else ""
                return f"Tidak ada file{where} pada bucket '{_SUPABASE_BUCKET}'."
            # Cap output if huge
            MAX_SHOW = 500
            shown = keys[:MAX_SHOW]
            more = "" if len(keys) <= MAX_SHOW else f"\n…(+{len(keys)-MAX_SHOW} lainnya)"
            return "Daftar file:\n" + "\n".join(shown) + more
        except RuntimeError as e:
            logger.error("Storage misconfiguration while listing: %s", e)
            return str(e)
        except Exception as e:
            logger.exception("Unexpected error listing storage files")
            return f"Gagal membaca daftar file: {e}"

    # general question
    if intent.intent == "GENERAL_QUESTION":
        use_gemini = getattr(settings, "USE_GEMINI", False) and getattr(settings, "GEMINI_API_KEY", None)
        if use_gemini:
            try:
                return ask_gemini_text(nl)
            except (GeminiBlocked, GeminiError) as e:
                logger.info("Gemini fallback to static help: %s", e)
        return ("Aku bisa: (1) total pasien, (2) jumlah pasien per uji klinis, "
                "(3) jumlah user (auth_user), (4) ambil file JSON dari Supabase Storage, mis. 'ambilkan saya data_1.json'.")

    # patients by trial: ensure name
    if intent.intent == "COUNT_PATIENTS_BY_TRIAL":
        trial = intent.args.get("trial_name")
        if not trial:
            return "Mohon sebutkan nama uji klinis yang dimaksud (contoh: 'berapa pasien uji klinis ABC')."

    # auth users count
    if intent.intent == "COUNT_AUTH_USERS":
        active_only = bool(intent.args.get("active_only"))
        try:
            if active_only:
                sql = "SELECT COUNT(*) FROM auth_user WHERE is_active = TRUE"
                n = _fetch_scalar(sql)
                return f"Total user aktif: {int(n or 0)}."
            else:
                sql = "SELECT COUNT(*) FROM auth_user"
                n = _fetch_scalar(sql)
                return f"Total user terdaftar: {int(n or 0)}."
        except Exception:
            logger.exception("DB error counting auth_user (active_only=%s)", active_only)
            return ("Tidak bisa mengakses tabel auth_user saat ini. "
                    "Periksa koneksi DB, kredensial, atau migrasi Django (lihat log).")

    # fetch JSON from storage
    if intent.intent == "GET_FILE_BY_NAME":
        filename = intent.args.get("filename")
        return _get_json_from_storage(filename)

    # SQL-backed intents (patients)
    try:
        sql, params = build_sql(intent.intent, intent.args)
    except Exception as e:
        logger.exception("Failed to build SQL for intent=%s args=%s", intent.intent, intent.args)
        return f"Gagal menyiapkan query untuk intent {intent.intent}: {e}"

    if intent.intent in ("TOTAL_PATIENTS", "COUNT_PATIENTS_BY_TRIAL"):
        try:
            n = _fetch_scalar(sql, params)
            n = int(n or 0)
        except Exception:
            logger.exception("DB error for intent=%s sql=%s params=%s", intent.intent, sql, params)
            return ("Tidak bisa mengakses database saat ini. "
                    "Periksa koneksi DB, kredensial, atau migrasi tabel (lihat log).")

        if intent.intent == "TOTAL_PATIENTS":
            return f"Total data pasien tersimpan: {n}."

        trial = intent.args.get("trial_name", "tertentu")
        return f"Jumlah pasien pada uji klinis {trial}: {n}."

    return "Maaf, aku belum bisa menjawab pertanyaan itu."


# ======== helpers for listing objects (placed at end for clarity) ========
def _is_folder_entry(item) -> bool:
    if isinstance(item, dict):
        t = (item.get("type") or item.get("kind") or "").lower()
        if t in ("folder", "directory"):
            return True
        # many SDK variants omit 'size' for folders
        if item.get("size") is None and not (item.get("name", "").endswith(".json")):
            return True
    return False


def _list_all_objects(bucket: str, prefix: str = "") -> List[str]:
    """Return a flat list of full object keys under `prefix`."""
    all_keys: List[str] = []
    to_visit = [prefix.strip("/")] if prefix else [""]
    visited = set()

    while to_visit:
        cur = to_visit.pop(0)
        if cur in visited:
            continue
        visited.add(cur)

        entries = _list_paths(bucket, cur or "")
        for it in entries:
            name = it.get("name") if isinstance(it, dict) else (it if isinstance(it, str) else None)
            if not name:
                continue
            full = f"{cur}/{name}" if cur else name
            if _is_folder_entry(it):
                to_visit.append(full)
            else:
                all_keys.append(full)
    return sorted(all_keys)
