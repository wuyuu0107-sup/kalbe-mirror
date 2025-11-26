# chat/guardrails.py

import logging
from pathlib import Path
from typing import Callable, Any

from django.conf import settings

# Optional NeMo Guardrails support
try:
    from nemoguardrails import LLMRails, RailsConfig  # type: ignore
except Exception:  # pragma: no cover - optional dependency path
    # NeMo not installed / incompatible: we fall back to Python-only guardrails.
    LLMRails = None  # type: ignore
    RailsConfig = None  # type: ignore

# Import Gemini error types from your llm.py
from .llm import GeminiError, GeminiBlocked

ERROR_MSG = "Mohon tanyakan pertanyaan yang relevan dengan data klinis."

log = logging.getLogger(__name__)


# ---------------- Config dir resolution ----------------

def _get_config_dir() -> Path:
    """
    Resolve NeMo Guardrails config directory.

    Priority:
    1. settings.RAILS_CONFIG_DIR if it exists
    2. <this_file_dir>/rails as default.
    """
    cfg = getattr(settings, "RAILS_CONFIG_DIR", None)
    if cfg:
        return Path(cfg)
    return Path(__file__).resolve().parent / "rails"


CONFIG_DIR = _get_config_dir()


# ---------------- Optional NeMo initialization ----------------

def _load_rails() -> Any:
    """
    Best-effort NeMo Guardrails loader.

    If anything fails, return None so Python-level guardrails take over.
    """
    if LLMRails is None or RailsConfig is None:
        log.info("NeMo Guardrails library not available; using Python-only guardrails.")
        return None

    try:
        if not CONFIG_DIR.exists():
            log.info(
                "NeMo Guardrails config dir %s not found; using Python-only guardrails.",
                CONFIG_DIR,
            )
            return None

        log.info("Loading NeMo Guardrails config from: %s", CONFIG_DIR)
        config = RailsConfig.from_path(str(CONFIG_DIR))
        rails = LLMRails(config)
        log.info("NeMo Guardrails initialized successfully.")
        return rails
    except Exception:
        log.exception(
            "Failed to initialize NeMo Guardrails from %s; "
            "falling back to Python-only guardrails.",
            CONFIG_DIR,
        )
        return None


# Global instance (may be None)
_rails_instance: Any = _load_rails()


def _get_rails() -> Any:
    """
    Backwards-compatible accessor used both by production code and unit tests.

    Tests patch this (chat.guardrails._get_rails) to inject a fake rails object.
    """
    return _rails_instance


# ---------------- Out-of-scope detection ----------------

_OUT_OF_SCOPE_KEYWORDS = [
    # existential / generic
    "meaning of life",
    "arti hidup",
    "apa arti hidup",
    "love",
    "cinta",
    "religion",
    "agama",
    # politics / opinions: don't send this to SQL/Gemini
    "trump",
    "biden",
    "prabowo",
    "jokowi",
    "presiden",
    "election",
    "pemilu",
    "politik",
    "politic",
    "opinion on",
]


def _is_out_of_scope(msg: str) -> bool:
    m = msg.lower()
    return any(k in m for k in _OUT_OF_SCOPE_KEYWORDS)


# ---------------- NeMo output normalization ----------------

def _extract_text(result: Any) -> str:
    """
    Normalize NeMo Guardrails output into a plain string.

    Rules (aligned with tests):
    - If result has a clear assistant content -> return it.
    - If result shape is unknown / no sanitized text -> return "" so we fallback.
    """

    if result is None:
        return ""

    # Direct string
    if isinstance(result, str):
        return result.strip()

    # Dict: look for known fields only
    if isinstance(result, dict):
        # 1) Direct "content"
        if "content" in result:
            return (result.get("content") or "").strip()

        # 2) OpenAI-style messages: [{"role": "assistant", "content": "..."}]
        messages = result.get("messages")
        if isinstance(messages, list):
            for msg in reversed(messages):
                if (
                    isinstance(msg, dict)
                    and msg.get("role") == "assistant"
                    and msg.get("content")
                ):
                    return (msg.get("content") or "").strip()

        # Any other dict shape = no sanitized response
        return ""

    # List of message dicts (just in case)
    if isinstance(result, list):
        for msg in reversed(result):
            if (
                isinstance(msg, dict)
                and msg.get("role") == "assistant"
                and msg.get("content")
            ):
                return (msg.get("content") or "").strip()
        # If no assistant messages found, fall through to final "" below.

    # Fallback for other types, or list with no assistant content:
    return ""


# ---------------- Safe backend wrapper ----------------

def _safe_backend_call(fallback_fn: Callable[[str], str], user_message: str) -> str:
    """
    Call backend answer function safely.

    Handles:
    - GeminiBlocked -> polite "stay in scope" message.
    - GeminiError (incl. empty_response) -> polite generic failure, no stacktrace.
    - Any other Exception -> logged once, user gets generic failure.
    """
    try:
        return fallback_fn(user_message)

    except GeminiBlocked as e:
        log.info("Gemini blocked prompt %r: %s", user_message, e)
        return ERROR_MSG

    except GeminiError as e:
        log.warning("Gemini could not answer %r: %s", user_message, e)
        return (
            "Maaf, sistem tidak dapat menjawab pertanyaan tersebut. "
            "Silakan ajukan pertanyaan yang lebih spesifik terkait data klinis."
        )

    except Exception as e:
        log.exception(
            "Backend fatal error while answering %r: %s",
            user_message,
            e,
        )
        return (
            "Maaf, terjadi masalah saat memproses pertanyaan ini di backend. "
            "Silakan coba lagi."
        )


# ---------------- Public entrypoint ----------------

def run_with_guardrails(user_message: str, fallback_fn: Callable[[str], str]) -> str:
    """
    Main entry used by views.py and tested in GuardrailsTests.

    Behavior:

    1. Empty input        -> ask for clinical question.
    2. Out-of-scope       -> fixed Indonesian warning (no backend).
    3. Else:
         - Use _get_rails() (tests can patch).
         - If no rails:
               -> backend via _safe_backend_call.
         - If rails exists:
               -> run it:
                    * warning text               -> return
                    * "__DEFER_TO_BACKEND__"     -> backend
                    * blank / unknown dict/etc.  -> backend
                    * anything else              -> return as sanitized.
    """

    text = (user_message or "").strip()
    if not text:
        return "Silakan ajukan pertanyaan terkait data klinis."

    # 1) Hard Python guardrail for obvious out-of-scope
    if _is_out_of_scope(text):
        return ERROR_MSG

    # 2) Get (possibly patched) rails instance.
    rails = _get_rails()

    # 3) If NeMo rails not available -> use backend safely.
    if rails is None:
        log.info("NeMo Guardrails not initialized; using Python-only guardrails.")
        return _safe_backend_call(fallback_fn, text)

    # 4) Try NeMo Guardrails.
    try:
        log.debug("Sending message to NeMo Guardrails: %r", text)
        result = rails.generate(messages=[{"role": "user", "content": text}])
        log.debug("Raw NeMo Guardrails result: %r", result)
    except Exception as e:
        log.exception("NeMo Guardrails runtime error; using backend fallback: %s", e)
        return _safe_backend_call(fallback_fn, text)

    gr_text = _extract_text(result)
    log.debug("Normalized NeMo Guardrails text: %r", gr_text)

    # Explicit out-of-scope reply from NeMo config.
    if gr_text == ERROR_MSG:
        return gr_text

    # Marker or blank/no sanitized -> let backend answer.
    if not gr_text or gr_text == "__DEFER_TO_BACKEND__":
        return _safe_backend_call(fallback_fn, text)

    # Low-level error message -> don't leak; use backend.
    if "encountered an error processing your request" in gr_text.lower():
        return _safe_backend_call(fallback_fn, text)

    # Otherwise trust NeMo's sanitized answer.
    return gr_text
