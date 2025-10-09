# chat/service.py
import re
from typing import Tuple, Any
from django.conf import settings
from .repo import DB
from .sqlgen import build_sql
from .llm import get_intent_json, GeminiError, GeminiBlocked, ask_gemini_text
from .intent import parse_intent, Intent

def _rule_based_intent(nl: str) -> Intent:
    s = (nl or "").lower().strip()
    if not s:
        raise ValueError("Pertanyaan kosong.")
    if ("total" in s and "pasien" in s) or ("semua" in s and "pasien" in s):
        return Intent(intent="TOTAL_PATIENTS", args={})
    if ("uji klinis" in s or "trial" in s) and ("berapa" in s or "jumlah" in s):
        m = re.search(r"(?:uji\s*klinis|trial)\s+([a-z0-9\-_/]+)", s)
        trial = m.group(1).upper() if m else None
        if not trial:
            # Explicitly ask for the trial name so we don't produce a vague answer
            raise ValueError("Mohon sebutkan nama uji klinis yang dimaksud.")
        return Intent(intent="COUNT_PATIENTS_BY_TRIAL", args={"trial_name": trial})
    # New: treat any other supported natural question as a GENERAL_QUESTION intent
    return Intent(intent="GENERAL_QUESTION", args={"question": nl})

def _smart_intent(nl: str) -> Intent:
    """
    Use Gemini when configured; on block/error, fall back to rules.
    Raise ValueError for unsupported/invalid questions so the view can return 400.
    """
    if settings.USE_GEMINI and getattr(settings, "GEMINI_API_KEY", None):
        try:
            raw = get_intent_json(nl)      # may raise GeminiError/GeminiBlocked
            return parse_intent(raw)       # may raise ValidationError -> bubble as ValueError
        except (GeminiBlocked, GeminiError) as e:
            # Fall back to rules instead of 502
            return _rule_based_intent(nl)
        except Exception as e:
            # Any parsing/validation error -> try rules, else surface as ValueError
            try:
                return _rule_based_intent(nl)
            except ValueError:
                raise ValueError(f"Pertanyaan tidak dapat dipahami: {e}")
    # No Gemini -> rules only
    return _rule_based_intent(nl)

def _fetch_scalar(sql: str, params: dict) -> int:
    row = DB().fetch_one(sql, params)
    if row is None:
        return 0
    # Support tuple/list/dict returns
    if isinstance(row, (list, tuple)):
        return int(row[0])
    if isinstance(row, dict):
        # try common keys
        for key in ("count", "total", "n", "sum"):
            if key in row:
                return int(row[key])
        # fallback to first value
        return int(next(iter(row.values())))
    return int(row)

def answer_question(nl: str) -> str:
    intent = _smart_intent(nl)

    if intent.intent == "GENERAL_QUESTION":
        if getattr(settings, "USE_GEMINI", False) and getattr(settings, "GEMINI_API_KEY", None):
            try:
                return ask_gemini_text(nl)
            except (GeminiBlocked, GeminiError):
                if settings.DEBUG:
                    return "[demo] LLM bermasalah, jadi ku-jawab singkat: " + nl[:200]
                raise
        return "General question received. Enable USE_GEMINI and GEMINI_API_KEY to answer free-text."

    # Validate required args early
    if intent.intent == "COUNT_PATIENTS_BY_TRIAL":
        trial = intent.args.get("trial_name")
        if not trial:
            raise ValueError("Mohon sebutkan nama uji klinis yang dimaksud.")

    # Build SQL and query
    sql, params = build_sql(intent.intent, intent.args)
    n = _fetch_scalar(sql, params)

    # Format answers
    if intent.intent == "TOTAL_PATIENTS":
        return f"Total data pasien tersimpan: {n}."
    trial = intent.args.get("trial_name", "tertentu")
    return f"Jumlah pasien pada uji klinis {trial}: {n}."
