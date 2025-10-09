# chat/llm.py
import os, re, json, logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FUTimeout

os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
os.environ.setdefault("GRPC_TRACE", "")

from django.conf import settings
import google.generativeai as genai

logger = logging.getLogger(__name__)

# ===== Konfigurasi dasar =====
MODEL_NAME = getattr(settings, "GEMINI_MODEL", None) or "gemini-2.5-flash"
GENCFG = {
    "temperature": 0,
    "response_mime_type": "application/json",
    "max_output_tokens": 256,
}
DEFAULT_DEADLINE_S = 12          # deadline network SDK
APP_TIMEOUT_S = 15               # guard di level aplikasi (harus <= proxy timeout)

PROMPT = (
    'Anda adalah agen ekstraksi INTENT. Keluarkan hanya JSON SATU BARIS dengan skema: '
    '{"intent":"<INTENT>","args":{...}} '
    'INTENT yang valid: '
    '- TOTAL_PATIENTS '
    '- COUNT_PATIENTS_BY_TRIAL  (args: {"trial_name":"<string>"}) '
    'Jika tidak cocok, keluarkan: {"intent":"UNSUPPORTED","args":{}}'
)

# ===== Exceptions khusus =====
class GeminiError(RuntimeError): ...
class GeminiBlocked(RuntimeError): ...
class GeminiRateLimited(RuntimeError): ...
class GeminiUnavailable(RuntimeError): ...
class GeminiConfigError(RuntimeError): ...

# ===== Lazy client =====
_model = None
def _get_model():
    global _model
    if _model is not None:
        return _model

    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        # Pilih salah satu: raise (fail fast) atau fallback UNSUPPORTED
        raise GeminiConfigError("GEMINI_API_KEY missing")

    try:
        genai.configure(api_key=api_key)
        _m = genai.GenerativeModel(MODEL_NAME)
    except Exception as e:
        raise GeminiConfigError(f"gemini_config_error: {e}")
    _model = _m
    return _model

# ===== Utils =====
_CODEFENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.I | re.M)
_JSON_SLOP = re.compile(r"^[\s\S]*?(\{.*\})[\s\S]*$", re.S)  # ambil JSON blok pertama

def _strip_to_json_line(text: str) -> str:
    if not text:
        return ""
    t = _CODEFENCE.sub("", text).strip()
    # ambil blok {...} pertama kalau ada sampah kiri/kanan
    m = _JSON_SLOP.match(t)
    if m:
        t = m.group(1).strip()
    # jadikan 1 baris
    return " ".join(t.split())

def _extract_text(resp) -> str:
    # urutan aman: iterate candidates → parts → resp.text
    try:
        for c in getattr(resp, "candidates", []) or []:
            for p in getattr(getattr(c, "content", None), "parts", []) or []:
                txt = getattr(p, "text", "") or ""
                if txt.strip():
                    return txt.strip()
    except Exception:
        pass
    return (getattr(resp, "text", "") or "").strip()

# ===== Public API =====
def get_intent_json(nl_question: str, *, request_id: str | None = None) -> str:
    """
    Balikkan STRING JSON SATU BARIS.
    Lempar GeminiError/GeminiBlocked/GeminiRateLimited/GeminiUnavailable/GeminiConfigError
    untuk ditangani di view (mapping ke 4xx/5xx/504 yang pas).
    """
    model = _get_model()

    def _call():
        return model.generate_content(
            [PROMPT, str(nl_question or "").strip()],
            generation_config=GENCFG,
            request_options={"timeout": DEFAULT_DEADLINE_S},
        )

    # Guard timeout di level aplikasi biar nggak bikin proxy 502
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_call)
        try:
            resp = fut.result(timeout=APP_TIMEOUT_S)
        except FUTimeout:
            logger.warning("gemini_app_timeout rid=%s", request_id)
            raise GeminiUnavailable("app_timeout")

    # Safety & rate limit handling
    fb = getattr(resp, "prompt_feedback", None)
    if fb and getattr(fb, "block_reason", None):
        raise GeminiBlocked(f"blocked: {fb.block_reason}")

    # Beberapa error di SDK nongol di candidates[0].finish_reason / safety_ratings
    try:
        cand0 = (getattr(resp, "candidates", []) or [None])[0]
        finish = getattr(cand0, "finish_reason", None)
        if str(finish).lower() in {"safety", "blocked"}:
            raise GeminiBlocked(f"finish_reason={finish}")
    except GeminiBlocked:
        raise
    except Exception:
        pass

    raw = _extract_text(resp)
    if not raw:
        raise GeminiError("empty_response")

    text = _strip_to_json_line(raw)

    # Validasi JSON & schema ringan
    try:
        obj = json.loads(text)
    except Exception as e:
        # Log sebagian buat forensik
        logger.warning("invalid_json rid=%s error=%s raw=%s", request_id, e, raw[:300])
        raise GeminiError(f"invalid_json: {e}")

    if not isinstance(obj, dict) or "intent" not in obj or "args" not in obj:
        raise GeminiError(f"bad_schema: got_keys={list(obj)[:5]}")

    # Normalisasi intent
    intent = str(obj.get("intent", "")).strip().upper()
    valid = {"TOTAL_PATIENTS", "COUNT_PATIENTS_BY_TRIAL", "UNSUPPORTED"}
    if intent not in valid:
        intent = "UNSUPPORTED"
    obj["intent"] = intent
    if "args" not in obj or not isinstance(obj["args"], dict):
        obj["args"] = {}

    # Kembalikan string satu baris
    return json.dumps(obj, separators=(",", ":"))
                      
def ask_gemini_text(prompt: str) -> str:
    """
    Minimal free-text answerer (no JSON). Raises GeminiError/GeminiBlocked on issues.
    """
    model = _get_model()
    try:
        resp = model.generate_content(
            [str(prompt or "").strip()],
            generation_config={"temperature": 0, "max_output_tokens": 256},
            request_options={"timeout": DEFAULT_DEADLINE_S},
        )
    except Exception as e:
        raise GeminiError(f"request_failed: {e}")

    fb = getattr(resp, "prompt_feedback", None)
    if fb and getattr(fb, "block_reason", None):
        raise GeminiBlocked(f"blocked: {fb.block_reason}")

    text = _extract_text(resp)
    if not text.strip():
        raise GeminiError("empty_response")
    return text.strip()
