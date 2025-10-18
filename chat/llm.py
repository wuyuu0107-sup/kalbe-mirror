# chat/llm.py
import os
import re
import json
import time
import logging
from random import random
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FUTimeout

# Quiet down gRPC noise from the SDK
os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
os.environ.setdefault("GRPC_TRACE", "")

from django.conf import settings
import google.generativeai as genai

logger = logging.getLogger(_name_)

# ===== Exceptions khusus =====
class GeminiError(RuntimeError): ...
class GeminiBlocked(RuntimeError): ...
class GeminiRateLimited(RuntimeError): ...
class GeminiUnavailable(RuntimeError): ...
class GeminiConfigError(RuntimeError): ...

# ===== Konfigurasi dasar (lebih robust) =====
MODEL_NAME = getattr(settings, "GEMINI_MODEL", None) or "gemini-2.5-flash"
GENCFG = {
    "temperature": 0,
    "response_mime_type": "application/json",
    "max_output_tokens": 256,
}

# Perhatikan batas reverse-proxy Anda. Pastikan APP_TIMEOUT_S < proxy timeout.
DEFAULT_DEADLINE_S = 18   # deadline network SDK (tiap request LLM)
APP_TIMEOUT_S = 22        # guard di level aplikasi

# Retry ringan untuk error sementara (429/5xx/timeout)
RETRY_MAX = 2                  # total 1 try + 2 retry = 3 attempt
RETRY_BASE_SLEEP = 0.6         # detik

# Fast-path: input sangat pendek / small talk tidak perlu panggil LLM
SMALL_TALK = {
    "hi", "hello", "bye", "thanks", "thank you",
    "makasih", "terima kasih"
}

PROMPT = (
    'Anda adalah agen ekstraksi INTENT. Balas HANYA JSON SATU BARIS TANPA MARKDOWN, '
    'tanpa teks lain. Skema: {"intent":"<INTENT>","args":{...}}. '
    'INTENT valid: TOTAL_PATIENTS; COUNT_PATIENTS_BY_TRIAL (args: {"trial_name":"<string>"}). '
    'Jika tidak cocok, keluarkan {"intent":"UNSUPPORTED","args":{}}.'
)

# ===== Lazy client =====
_model = None
def _get_model():
    """Create and cache the Gemini model client."""
    global _model
    if _model is not None:
        return _model

    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        raise GeminiConfigError("GEMINI_API_KEY missing")

    try:
        genai.configure(api_key=api_key)
        _m = genai.GenerativeModel(MODEL_NAME)
    except Exception as e:
        raise GeminiConfigError(f"gemini_config_error: {e}")
    _model = _m
    return _model

# ===== Regex & utils =====
_CODEFENCE = re.compile(r"^\s*(?:json)?\s*|\s*\s*$", re.I | re.M)
_JSON_SLOP = re.compile(r"^[\s\S]?(\{.\})[\s\S]*$", re.S)  # ambil JSON blok pertama
_TRAILING_COMMAS = re.compile(r",\s*([}\]])")                # hapus koma menggantung
_SINGLE_QUOTES = re.compile(r'(?<!\\)\'')                    # ubah ' -> " (simple)

def _strip_to_json_line(text: str) -> str:
    """Buang codefence & sampah kiri/kanan, ambil blok {...} pertama, jadi 1 baris."""
    if not text:
        return ""
    t = _CODEFENCE.sub("", text).strip()
    m = _JSON_SLOP.match(t)
    if m:
        t = m.group(1).strip()
    return " ".join(t.split())

def _extract_text(resp) -> str:
    """Ambil teks dari response Gemini dengan aman."""
    try:
        for c in getattr(resp, "candidates", []) or []:
            for p in getattr(getattr(c, "content", None), "parts", []) or []:
                txt = getattr(p, "text", "") or ""
                if txt.strip():
                    return txt.strip()
    except Exception:
        pass
    return (getattr(resp, "text", "") or "").strip()

def _is_retryable_error(exc: Exception) -> bool:
    s = str(exc).lower()
    return any(k in s for k in [
        "deadline", "timeout", "unavailable", "temporar", "try again",
        "rate", "429", "connection reset", "transport error", "internal"
    ])

def _with_retries(call_fn):
    """Jalankan call_fn dengan retry + exponential backoff untuk error sementara."""
    last_exc = None
    for i in range(RETRY_MAX + 1):
        try:
            return call_fn()
        except Exception as e:
            last_exc = e
            if not _is_retryable_error(e) or i == RETRY_MAX:
                raise
            sleep_s = RETRY_BASE_SLEEP * (2 ** i) * (1 + 0.25 * random())
            time.sleep(sleep_s)
    raise last_exc  # pragma: no cover

def _try_parse_json(text: str):
    """Parse JSON; jika gagal, lakukan perbaikan ringan lalu coba lagi."""
    try:
        return json.loads(text)
    except Exception:
        pass
    t = _strip_to_json_line(text)
    if not t:
        return None
    # Perbaikan ringan
    t = _TRAILING_COMMAS.sub(r"\1", t)
    t = _SINGLE_QUOTES.sub('"', t)
    try:
        return json.loads(t)
    except Exception:
        return None

def _fastpath_intent(nl_question: str) -> str | None:
    """Hindari panggilan LLM untuk input trivial/pendek."""
    q = (nl_question or "").strip().lower()
    if not q:
        return json.dumps({"intent": "UNSUPPORTED", "args": {}})
    if q in SMALL_TALK or len(q.split()) <= 2:
        return json.dumps({"intent": "UNSUPPORTED", "args": {}})
    return None

# ===== Public API =====
def get_intent_json(nl_question: str, *, request_id: str | None = None) -> str:
    """
    Mengembalikan STRING JSON SATU BARIS sesuai skema intent.
    Lempar GeminiError/GeminiBlocked/GeminiUnavailable/GeminiConfigError untuk ditangani di view.
    """
    # Fast-path: jangan pukul LLM untuk pertanyaan sangat pendek/small talk
    fp = _fastpath_intent(nl_question)
    if fp is not None:
        return fp

    model = _get_model()

    def _call():
        return model.generate_content(
            [PROMPT, str(nl_question or "").strip()],
            generation_config=GENCFG,
            request_options={"timeout": DEFAULT_DEADLINE_S},
        )

    # Guard timeout aplikasi + retry internal
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(lambda: _with_retries(_call))
        try:
            resp = fut.result(timeout=APP_TIMEOUT_S)
        except FUTimeout:
            logger.warning("gemini_app_timeout rid=%s", request_id)
            raise GeminiUnavailable("app_timeout")

    # Safety / block handling
    fb = getattr(resp, "prompt_feedback", None)
    if fb and getattr(fb, "block_reason", None):
        raise GeminiBlocked(f"blocked: {fb.block_reason}")

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

    # Parse + repair
    obj = _try_parse_json(raw)
    if obj is None:
        logger.warning("invalid_json rid=%s raw=%s", request_id, raw[:300])
        raise GeminiError("invalid_json")

    # Schema guard + normalisasi
    if not isinstance(obj, dict):
        raise GeminiError("bad_schema: not dict")
    obj.setdefault("intent", "UNSUPPORTED")
    obj.setdefault("args", {})
    if not isinstance(obj["args"], dict):
        obj["args"] = {}

    intent = str(obj.get("intent", "")).strip().upper()
    valid = {"TOTAL_PATIENTS", "COUNT_PATIENTS_BY_TRIAL", "UNSUPPORTED"}
    if intent not in valid:
        intent = "UNSUPPORTED"
    obj["intent"] = intent

    return json.dumps(obj, separators=(",", ":"))

def ask_gemini_text(prompt: str) -> str:
    """
    Minimal free-text answerer (no JSON).
    Raises GeminiError/GeminiBlocked/GeminiUnavailable on issues.
    """
    model = _get_model()

    def _call():
        return model.generate_content(
            [str(prompt or "").strip()],
            generation_config={"temperature": 0, "max_output_tokens": 256},
            request_options={"timeout": DEFAULT_DEADLINE_S},
        )

    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(lambda: _with_retries(_call))
        try:
            resp = fut.result(timeout=APP_TIMEOUT_S)
        except FUTimeout:
            logger.warning("gemini_app_timeout_text")
            raise GeminiUnavailable("app_timeout")

    fb = getattr(resp, "prompt_feedback", None)
    if fb and getattr(fb, "block_reason", None):
        raise GeminiBlocked(f"blocked: {fb.block_reason}")

    text = _extract_text(resp)
    if not text.strip():
        raise GeminiError("empty_response")
    return text.strip()