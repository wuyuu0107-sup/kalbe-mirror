from typing import Tuple, List

ALLOWED = {
    "patients": {"id","trial_id","sex","age"},
    "trials": {"id","name"},
    # opsional: ini hanya dokumentasi kolom, tidak dipakai langsung
}

def build_sql(intent: str, args: dict) -> Tuple[str, List]:
    if intent == "TOTAL_PATIENTS":
        return "SELECT COUNT(*) FROM patients", []

    if intent == "COUNT_PATIENTS_BY_TRIAL":
        return (
            "SELECT COUNT(*) FROM patients "
            "WHERE trial_id = (SELECT id FROM trials WHERE name = %s LIMIT 1)",
            [args.get("trial_name")]
        )

    # 🔧 Intent baru: ambil JSON file berdasarkan nama
    if intent == "GET_FILE_BY_NAME":
        return (
            "SELECT content FROM files WHERE name = %s LIMIT 1",
            [args.get("filename")]
        )

    raise ValueError("Unsupported intent")
