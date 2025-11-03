from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Dict
import json
import re


# =========================
# Structured Intent (optional JSON mode)
# =========================

class Intent(BaseModel):
    intent: str = Field(...)
    args: Dict = Field(default_factory=dict)


ALLOWED_INTENTS = {
    # Keep/extend these if you have rule-based intents handled deterministically
    "TOTAL_PATIENTS",
    "COUNT_PATIENTS_BY_TRIAL",
    "GET_FILE_BY_NAME",
    "LIST_BUCKETS",
    "LIST_STORAGE_FILES",
    "SUPABASE_WHOAMI",
    "COUNT_AUTH_USERS",
}


def parse_intent(raw_text: str) -> Intent:
    """
    Parse a JSON dict produced by an LLM into a validated Intent.
    Raises:
        ValueError if intent not in whitelist or JSON invalid.
    """
    data = json.loads(raw_text)
    obj = Intent(**data)
    if obj.intent not in ALLOWED_INTENTS:
        raise ValueError(f"Intent not allowed: {obj.intent}")
    return obj


# =========================
# Lightweight Semantic Prompt Router
# =========================

class PromptRouter:
    """
    Route a natural-language message into a coarse semantic bucket.

    Buckets:
      - "database_query": likely a data/SQL-style question
      - "clinical_info": asks about patients/trials/metrics semantically (non-SQL phrasing)
      - "instruction": "explain/teach/how to"
      - "general_conversation": small talk, chit-chat
      - "oos": out-of-scope (guardrail)

    Keep it fast and dependency-free (regex + keywords) for server use.
    """

    DB_HINT_WORDS = (
        # English
        "how many", "count", "show me", "list", "average", "sum", "min", "max",
        "filter", "group", "trend", "between", "per trial", "by trial", "by patient",
        # Indonesian
        "berapa", "hitung", "tampilkan", "daftar", "rata-rata", "jumlah",
        "per uji", "per trial", "rata rata",
    )

    CLINICAL_WORDS = (
        "patient", "patients", "trial", "clinical", "sgot", "sgpt", "gender", "age",
        "dokumen", "berkas", "ocr", "kadar", "nilai", "dokter", "berat", "tinggi",
    )

    INSTRUCTION_WORDS = (
        "explain", "jelaskan", "how to", "teach", "mengapa", "why", "cara", "tutorial",
    )

    SMALLTALK_WORDS = (
        "hello", "hi", "thanks", "terima kasih", "who are you", "help", "hai",
    )

    OOS_PATTERNS = (
        r"\bmeaning of life\b",
        r"\binvestment advice\b",
        r"\bcrypto signals\b",
    )

    def route(self, text: str) -> str:
        s = (text or "").strip().lower()
        if not s:
            return "general_conversation"

        # Hard out-of-scope guard
        for pat in self.OOS_PATTERNS:
            if re.search(pat, s):
                return "oos"

        # Heuristic buckets
        if any(w in s for w in self.DB_HINT_WORDS):
            return "database_query"
        if any(w in s for w in self.CLINICAL_WORDS):
            return "clinical_info"
        if any(w in s for w in self.INSTRUCTION_WORDS):
            return "instruction"
        if any(w in s for w in self.SMALLTALK_WORDS):
            return "general_conversation"

        # Default bias: analytics phrasing → database_query
        if re.search(r"\b(show|list|how\s+many|count|average|avg)\b", s):
            return "database_query"

        return "general_conversation"
