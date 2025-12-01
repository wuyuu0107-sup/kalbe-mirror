from .field_extractors import (
    extract_demography_fields,
    extract_vital_signs_fields,
    extract_medical_history_fields,
    extract_lab_results_fields
)


def map_ocr_json_to_patient(json_data):
    """
    Maps nested OCR JSON structure to flat Patient model fields.
    
    Args:
        json_data (dict): Nested JSON with DEMOGRAPHY, MEDICAL_HISTORY, VITAL_SIGNS, etc.
        
    Returns:
        dict: Flat dictionary with Patient model field names and values
    """
    demography = json_data.get('DEMOGRAPHY', {})
    medical_history = json_data.get('MEDICAL_HISTORY', {})
    vital_signs = json_data.get('VITAL_SIGNS', {})
    hematology = json_data.get('HEMATOLOGY', {})
    clinical_chemistry = json_data.get('CLINICAL_CHEMISTRY', {})
    
    patient_data = {}
    patient_data.update(extract_demography_fields(demography))
    patient_data.update(extract_vital_signs_fields(vital_signs))
    patient_data.update(extract_medical_history_fields(medical_history))
    patient_data.update(extract_lab_results_fields(hematology, clinical_chemistry))
    
    return patient_data

