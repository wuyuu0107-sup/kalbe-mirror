from typing import Tuple, List

ALLOWED = {
    "patients": {"id","trial_id","sex","age"},
    "trials": {"id","name"},
}

def build_sql(intent: str, args: dict) -> Tuple[str, List]:
    if intent == "TOTAL_PATIENTS":
        return "SELECT COUNT(*) FROM patients", []
    if intent == "COUNT_PATIENTS_BY_TRIAL":
        # Kita pakai nama → id lewat subquery aman
        return (
            "SELECT COUNT(*) FROM patients "
            "WHERE trial_id = (SELECT id FROM trials WHERE name = %s LIMIT 1)",
            [args.get("trial_name")]
        )
    raise ValueError("Unsupported intent")
