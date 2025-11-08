# chat/llm.py
import os
import re
import json
import time
import logging
from dataclasses import dataclass
from typing import Callable, Protocol, Sequence, Optional
from random import random
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FUTimeout

# Quiet down gRPC noise from the SDK
os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
os.environ.setdefault("GRPC_TRACE", "")

from django.conf import settings
import google.generativeai as genai

logger = logging.getLogger(__name__)

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

# ===== Lazy client (kept for backward-compat with existing tests) =====
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

# ===== Regex & utils (kept names for test compatibility) =====
# Remove leading ```json / trailing ``` fences line-by-line
_CODEFENCE = re.compile(r"^\s*```(?:json)?\s*$|^\s*```\s*$", re.I | re.M)

# Find the outermost-looking JSON object: from the first '{' to the last '}'
_JSON_SLOP = re.compile(r"\{[\s\S]*\}", re.S)

# Remove dangling commas before } or ]
_TRAILING_COMMAS = re.compile(r",\s*([}\]])")

# Convert single quotes to double quotes (simple heuristic)
_SINGLE_QUOTES = re.compile(r"(?<!\\)'")


def _strip_to_json_line(text: str) -> str:
    """Buang codefence & sampah kiri/kanan, ambil blok {...} pertama, jadi 1 baris."""
    if not text:
        return ""
    # Remove code fences and surrounding whitespace
    t = _CODEFENCE.sub("", text).strip()
    # Extract the JSON object from anywhere in the text
    m = _JSON_SLOP.search(t)
    if m:
        t = m.group(0).strip()
    # Normalize spacing to one line
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
    # NOTE: Some SDK versions raise if `resp.text` is accessed without parts.
    # Use getattr pattern to avoid raising here; .strip() on "" is safe.
    try:
        return (getattr(resp, "text", "") or "").strip()
    except Exception:
        return ""


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


# ===== SOLID refactor: small, focused components =====
class LLMClient(Protocol):
    def generate(self, parts: Sequence[str], *, generation_config: dict, timeout_s: int) -> object: ...


@dataclass
class ResilientCaller:
    """Owns timeout + retry mechanics (dependency for higher-level use cases)."""
    app_timeout_s: int = APP_TIMEOUT_S

    def run(self, fn: Callable[[], object]) -> object:
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(lambda: _with_retries(fn))
            try:
                return fut.result(timeout=self.app_timeout_s)
            except FUTimeout:
                # Keep log format for existing tests
                logger.warning("gemini_app_timeout rid=%s", None)
                raise GeminiUnavailable("app_timeout")


class GeminiLLMClient:
    """Adapter over google.generativeai GenerativeModel (Dependency Inversion)."""
    def __init__(self, model=None):
        self._model = model or _get_model()

    def generate(self, parts: Sequence[str], *, generation_config: dict, timeout_s: int) -> object:
        return self._model.generate_content(
            list(parts),
            generation_config=generation_config,
            request_options={"timeout": timeout_s},
        )


class IntentJsonNormalizer:
    """Single Responsibility: normalize/repair LLM JSON to Python object."""
    def parse(self, raw: str) -> Optional[dict]:
        return _try_parse_json(raw)


class IntentExtractor:
    """Coordinates LLM call, safety checks, text extraction, and JSON normalization."""
    def __init__(self, llm: LLMClient, caller: ResilientCaller, normalizer: IntentJsonNormalizer):
        self.llm = llm
        self.caller = caller
        self.normalizer = normalizer

    def _check_block(self, resp) -> None:
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
            # swallow shape issues
            pass

    def infer_intent(self, question: str, request_id: str | None = None) -> dict:
        def _call():
            return self.llm.generate(
                [PROMPT, str(question or "").strip()],
                generation_config=GENCFG,
                timeout_s=DEFAULT_DEADLINE_S,
            )

        resp = self.caller.run(_call)
        self._check_block(resp)

        raw = _extract_text(resp)
        if not raw:
            raise GeminiError("empty_response")

        obj = self.normalizer.parse(raw)
        if obj is None:
            logger.warning("invalid_json rid=%s raw=%s", request_id, raw[:300])
            raise GeminiError("invalid_json")
        if not isinstance(obj, dict) or "intent" not in obj or "args" not in obj or not isinstance(obj["args"], dict):
            raise GeminiError("bad_schema")
        return {"intent": str(obj["intent"]), "args": obj["args"]}

    def free_text(self, prompt: str) -> str:
        def _call():
            return self.llm.generate(
                [str(prompt or "").strip()],
                generation_config={"temperature": 0, "max_output_tokens": 256},
                timeout_s=DEFAULT_DEADLINE_S,
            )

        try:
            resp = self.caller.run(_call)
        except GeminiUnavailable:
            # keep the separate log line for existing tests
            logger.warning("gemini_app_timeout_text")
            raise
        except Exception as e:
            # translate any SDK/transport failure to GeminiError
            raise GeminiError(str(e))

        fb = getattr(resp, "prompt_feedback", None)
        if fb and getattr(fb, "block_reason", None):
            raise GeminiBlocked(f"blocked: {fb.block_reason}")

        text = _extract_text(resp).strip()
        if not text:
            raise GeminiError("empty_response")
        return text


# ===== Public API (kept signatures, now delegating to the SOLID components) =====
def get_intent_json(nl_question: str, *, request_id: str | None = None) -> str:
    """
    Mengembalikan STRING JSON SATU BARIS sesuai skema intent.
    Lempar GeminiError/GeminiBlocked/GeminiUnavailable/GeminiConfigError untuk ditangani di view.
    """
    # Keep fast-path available for future use; tests currently call LLM directly.
    # fp = _fastpath_intent(nl_question)
    # if fp is not None:
    #     return fp

    extractor = IntentExtractor(
        llm=GeminiLLMClient(),
        caller=ResilientCaller(app_timeout_s=APP_TIMEOUT_S),
        normalizer=IntentJsonNormalizer(),
    )
    obj = extractor.infer_intent(nl_question, request_id=request_id)
    return json.dumps(obj, separators=(",", ":"))


def ask_gemini_text(prompt: str, *, retry_on_empty: bool = True) -> str:
    """
    Minimal free-text answerer (no JSON).
    Raises:
      - GeminiUnavailable on app timeout
      - GeminiBlocked on safety block
      - GeminiError on SDK/transport failure or empty text after retry
    """
    model = _get_model()

    def _call():
        return model.generate_content(
            [str(prompt or "").strip()],
            generation_config={"temperature": 0, "max_output_tokens": 256},
            request_options={"timeout": DEFAULT_DEADLINE_S},
        )

    def _once() -> str:
        # single guarded attempt (respect app-level timeout + internal retry/backoff)
        with ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(lambda: _with_retries(_call))
            try:
                resp = fut.result(timeout=APP_TIMEOUT_S)
            except FUTimeout:
                logger.warning("gemini_app_timeout_text")
                raise GeminiUnavailable("app_timeout")
            except Exception as e:
                # translate any SDK/transport failure to GeminiError
                raise GeminiError(str(e))

        fb = getattr(resp, "prompt_feedback", None)
        if fb and getattr(fb, "block_reason", None):
            raise GeminiBlocked(f"blocked: {fb.block_reason}")

        # safe extraction; never touch resp.text directly
        text = _extract_text(resp).strip()
        return text

    text = _once()
    if not text and retry_on_empty:
        # tiny jitter to avoid immediate duplicate; keep it short to stay within app timeout
        try:
            time.sleep(0.15)
        except Exception:
            pass
        text = _once()

    if not text:
        raise GeminiError("empty_response")
    return text
