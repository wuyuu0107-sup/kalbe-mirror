from pydantic import BaseModel, Field
from typing import Dict
import json

class Intent(BaseModel):
    intent: str = Field(...)
    args: Dict = Field(default_factory=dict)

ALLOWED_INTENTS = {"TOTAL_PATIENTS", "COUNT_PATIENTS_BY_TRIAL", "GET_FILE_BY_NAME"}

def parse_intent(raw_text: str) -> Intent:
    data = json.loads(raw_text)
    obj = Intent(**data)
    if obj.intent not in ALLOWED_INTENTS:
        raise ValueError("Intent not allowed")
    return obj