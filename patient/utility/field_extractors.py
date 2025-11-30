from .converters import (
    parse_date_string,
    safe_float_conversion,
    safe_int_conversion,
    extract_result_value
)

def extract_demography_fields(demography):
    """
    Extracts demographic fields from DEMOGRAPHY section.
    
    Args:
        demography: DEMOGRAPHY section dict
        
    Returns:
        dict with demographic patient fields
    """
    return {
        'sin': demography.get('sin'),
        'name': demography.get('name'),
        'subject_initials': demography.get('subject_initials'),
        'gender': demography.get('gender'),
        'date_of_birth': parse_date_string(demography.get('date_of_birth')),
        'address': demography.get('address', ''),
        'phone_number': demography.get('phone_number', ''),
        'age': safe_int_conversion(demography.get('age')),
        'height': safe_float_conversion(demography.get('height_cm')),
        'weight': safe_float_conversion(demography.get('weight_kg')),
        'bmi': safe_float_conversion(demography.get('bmi')),
    }


def extract_vital_signs_fields(vital_signs):
    """
    Extracts vital signs fields from VITAL_SIGNS section.
    
    Args:
        vital_signs: VITAL_SIGNS section dict
        
    Returns:
        dict with vital signs patient fields
    """
    return {
        'systolic': safe_int_conversion(vital_signs.get('systolic_bp')),
        'diastolic': safe_int_conversion(vital_signs.get('diastolic_bp')),
    }


def extract_medical_history_fields(medical_history):
    """
    Extracts medical history fields from MEDICAL_HISTORY section.
    
    Args:
        medical_history: MEDICAL_HISTORY section dict
        
    Returns:
        dict with medical history patient fields
    """
    return {
        'smoking_habit': medical_history.get('smoking_habit', ''),
        'smoker': safe_int_conversion(medical_history.get('smoker_cigarettes_per_day'), default=0),
        'drinking_habit': medical_history.get('drinking_habit', ''),
    }


def extract_lab_results_fields(hematology, clinical_chemistry):
    """
    Extracts lab results from HEMATOLOGY and CLINICAL_CHEMISTRY sections.
    
    Args:
        hematology: HEMATOLOGY section dict
        clinical_chemistry: CLINICAL_CHEMISTRY section dict
        
    Returns:
        dict with lab results patient fields
    """
    return {
        'hemoglobin': safe_float_conversion(
            extract_result_value(hematology.get('hemoglobin', {}))
        ),
        'random_blood_glucose': safe_float_conversion(
            extract_result_value(clinical_chemistry.get('random_blood_glucose', {}))
        ),
        'sgot': safe_float_conversion(
            extract_result_value(clinical_chemistry.get('sgot', {}))
        ),
        'sgpt': safe_float_conversion(
            extract_result_value(clinical_chemistry.get('sgpt', {}))
        ),
        'alkaline_phosphatase': safe_float_conversion(
            extract_result_value(clinical_chemistry.get('alkaline_phosphatase', {}))
        ),
    }
