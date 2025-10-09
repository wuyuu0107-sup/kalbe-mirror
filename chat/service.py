# chat/service.py
import re, json
from django.conf import settings
from .repo import DB
from .sqlgen import build_sql
from .llm import get_intent_json, GeminiError, GeminiBlocked
from .intent import parse_intent, Intent

def _rule_based_intent(nl: str) -> Intent:
    s = (nl or "").lower()
    if ("total" in s and "pasien" in s) or ("semua" in s and "pasien" in s):
        return Intent(intent="TOTAL_PATIENTS", args={})
    if ("uji klinis" in s or "trial" in s) and ("berapa" in s or "jumlah" in s):
        m = re.search(r"(uji\s*klinis|trial)\s+([a-z0-9\-_/]+)", s)
        return Intent(intent="COUNT_PATIENTS_BY_TRIAL", args={"trial_name": m.group(2).upper() if m else None})
    raise ValueError("Pertanyaan belum didukung.")

def _get_intent(nl: str) -> Intent:
    if settings.USE_GEMINI and settings.GEMINI_API_KEY:
        raw = get_intent_json(nl)     # bisa lempar GeminiError/Blocked
        return parse_intent(raw)      # validasi pydantic
    return _rule_based_intent(nl)

def answer_question(nl: str) -> str:
    intent = _get_intent(nl)
    sql, params = build_sql(intent.intent, intent.args)
    n = (DB().fetch_one(sql, params) or [0])[0]
    if intent.intent == "TOTAL_PATIENTS":
        return f"Total data pasien tersimpan: {n}."
    trial = intent.args.get("trial_name") or "tertentu"
    return f"Jumlah pasien pada uji klinis {trial}: {n}."
