from typing import Dict, Any, Optional
import re
from datetime import datetime

SECTION_ORDER = [
    "DEMOGRAPHY",
    "MEDICAL_HISTORY",
    "VITAL_SIGNS",
    "SEROLOGY",
    "URINALYSIS",
    "HEMATOLOGY",
    "CLINICAL_CHEMISTRY",
]

MEAS_KEYS = ("Hasil", "Nilai Rujukan", "Satuan", "Metode")

URINALYSIS_FIELDS = [
    "ph", "density", "glucose", "ketone", "urobilinogen",
    "bilirubin", "blood", "leucocyte_esterase", "nitrite",
]
HEMATOLOGY_FIELDS = [
    "hemoglobin", "hematocrit", "leukocyte", "erythrocyte", "thrombocyte", "esr",
]
CHEMISTRY_FIELDS = [
    "bilirubin_total", "alkaline_phosphatase", "sgot", "sgpt", "ureum", "creatinine", "random_blood_glucose",
]

_DATE_FMTS = [
    "%d/%b/%Y", "%d-%b-%Y", "%d/%B/%Y", "%d-%B-%Y",
    "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y",
]


def order_sections(d: dict) -> dict:
    head = {k: d[k] for k in SECTION_ORDER if k in d}
    tail = {k: v for k, v in d.items() if k not in head}
    return {**head, **tail}


def _meas_template():
    return {"Hasil": None, "Nilai Rujukan": None, "Satuan": None, "Metode": None}


def _to_str(x):
    if x is None:
        return None
    return str(x)


def _norm_date(s):
    if not s:
        return None
    if isinstance(s, (int, float)):
        s = str(s)
    s = s.strip()
    
    m = re.match(r"^\d{2}/[A-Za-z]{3}/\d{4}$", s)
    if m:
        d, mon, y = s.split("/")
        return f"{d}/{mon[:3].upper()}/{y}"
    
    for fmt in _DATE_FMTS:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%d/%b/%Y").upper()
        except Exception:
            continue
    
    return s


def _as_meas(val, default_method=None):
    out = _meas_template()
    if isinstance(val, dict):
        for k in MEAS_KEYS:
            if k in val:
                out[k] = _to_str(val[k])
        for k, v in val.items():
            if k not in out:
                out[k] = v
    elif val is not None:
        out["Hasil"] = _to_str(val)
    if default_method and not out.get("Metode"):
        out["Metode"] = default_method
    return out


def _ensure_section(obj, fields, default_method=None):
    for f in fields:
        val = obj.get(f) if isinstance(obj, dict) else None
        obj[f] = _as_meas(val, default_method=default_method)


def _default_payload():
    return {
        "DEMOGRAPHY": {
            "subject_initials": None, "sin": None, "study_drug": None,
            "screening_date": None, "gender": None, "date_of_birth": None,
            "age": None, "weight_kg": None, "height_cm": None, "bmi": None,
        },
        "MEDICAL_HISTORY": {"smoker_cigarettes_per_day": None},
        "VITAL_SIGNS": {"systolic_bp": None, "diastolic_bp": None, "heart_rate": None},
        "SEROLOGY": {"hbsag": None, "hcv": None, "hiv": None},
        "URINALYSIS": {k: _meas_template() for k in URINALYSIS_FIELDS},
        "HEMATOLOGY": {k: _meas_template() for k in HEMATOLOGY_FIELDS},
        "CLINICAL_CHEMISTRY": {k: _meas_template() for k in CHEMISTRY_FIELDS},
    }


def normalize_payload(extracted: dict) -> dict:
    base = _default_payload()
    
    if not isinstance(extracted, dict):
        return _build_ordered_output(base, {})
    
    norm = _normalize_section_keys(extracted)
    _merge_simple_sections(norm, base)
    _process_serology(norm.get("SEROLOGY", {}), base["SEROLOGY"])
    _process_measurement_sections(norm, base)
    _process_demography(base["DEMOGRAPHY"])
    _process_vital_signs(base["VITAL_SIGNS"])
    
    extras = _collect_extra_sections(norm)
    return _build_ordered_output(base, extras)


def _normalize_section_keys(extracted: Dict[str, Any]) -> Dict[str, Any]:
    norm = {}
    mapping = {
        "DEMOGRAPHY": "DEMOGRAPHY",
        "MEDICAL_HISTORY": "MEDICAL_HISTORY",
        "VITAL_SIGNS": "VITAL_SIGNS",
        "SEROLOGY": "SEROLOGY",
        "URINALYSIS": "URINALYSIS",
        "HEMATOLOGY": "HEMATOLOGY",
        "CLINICAL_CHEMISTRY": "CLINICAL_CHEMISTRY",
    }
    
    for k, v in extracted.items():
        ku = k.upper().replace(" ", "_")
        norm[mapping.get(ku, k)] = v
    
    return norm


def _merge_simple_sections(norm: Dict[str, Any], base: Dict[str, Any]) -> None:
    for sec in ("DEMOGRAPHY", "MEDICAL_HISTORY", "VITAL_SIGNS"):
        if isinstance(norm.get(sec), dict):
            base[sec].update(norm[sec])


def _process_demography(demo: Dict[str, Any]) -> None:
    demo["screening_date"] = _norm_date(demo.get("screening_date"))
    demo["date_of_birth"] = _norm_date(demo.get("date_of_birth"))
    
    demo["age"] = _convert_age_to_int(demo.get("age"))
    
    for k in ("weight_kg", "height_cm", "bmi"):
        if demo.get(k) is not None:
            demo[k] = _to_str(demo[k])


def _convert_age_to_int(age_value) -> Optional[int]:
    try:
        return int(age_value) if age_value not in (None, "") else None
    except Exception:
        return None


def _process_vital_signs(vitals: Dict[str, Any]) -> None:
    for k in ("systolic_bp", "diastolic_bp", "heart_rate"):
        if vitals.get(k) is not None:
            vitals[k] = _to_str(vitals[k])


def _process_serology(serology: Dict[str, Any], base: Dict[str, Any]) -> None:
    if not isinstance(serology, dict):
        return
    
    for k in base.keys():
        base[k] = _serology_str(serology.get(k))


def _serology_str(x):
    if x is None:
        return None
    if isinstance(x, dict):
        for key in ("Hasil", "hasil", "value", "Value", "result", "Result"):
            if key in x and x[key] is not None:
                return str(x[key])
        return str(x)
    return str(x)


def _process_measurement_sections(norm: Dict[str, Any], base: Dict[str, Any]) -> None:
    sections = [
        ("URINALYSIS", URINALYSIS_FIELDS, "Carik Celup"),
        ("HEMATOLOGY", HEMATOLOGY_FIELDS, None),
        ("CLINICAL_CHEMISTRY", CHEMISTRY_FIELDS, None),
    ]
    
    for sec, fields, default_method in sections:
        if isinstance(norm.get(sec), dict):
            base[sec].update(norm[sec])
        _ensure_section(base[sec], fields, default_method=default_method)


def _collect_extra_sections(norm: Dict[str, Any]) -> Dict[str, Any]:
    known_sections = {
        "DEMOGRAPHY", "MEDICAL_HISTORY", "VITAL_SIGNS",
        "SEROLOGY", "URINALYSIS", "HEMATOLOGY", "CLINICAL_CHEMISTRY"
    }
    return {k: v for k, v in norm.items() if k not in known_sections}


def _build_ordered_output(base: Dict[str, Any], extras: Dict[str, Any]) -> Dict[str, Any]:
    ordered = {
        "DEMOGRAPHY": base["DEMOGRAPHY"],
        "MEDICAL_HISTORY": base["MEDICAL_HISTORY"],
        "VITAL_SIGNS": base["VITAL_SIGNS"],
        "SEROLOGY": base["SEROLOGY"],
        "URINALYSIS": base["URINALYSIS"],
        "HEMATOLOGY": base["HEMATOLOGY"],
        "CLINICAL_CHEMISTRY": base["CLINICAL_CHEMISTRY"],
    }
    ordered.update(extras)
    return ordered