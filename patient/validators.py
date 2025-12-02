"""
Enhanced input validators for patient data.
Provides comprehensive validation for patient records including type, range, and format checks.
"""
from django.core.validators import validate_email, RegexValidator
from django.core.exceptions import ValidationError


def validate_patient_data(data):
    """
    Comprehensive patient data validation with allow-list approach.
    
    Args:
        data (dict): Patient data to validate
        
    Returns:
        dict or None: Dictionary of errors if validation fails, None if all valid
    """
    errors = {}
    
    # 1. Email validation
    if 'email' in data and data['email']:
        try:
            validate_email(data['email'])
        except ValidationError:
            errors['email'] = 'Invalid email format'
    
    # 2. Age validation (reasonable range)
    if 'age' in data and data['age'] is not None:
        try:
            age = int(data['age'])
            if age < 0 or age > 150:
                errors['age'] = 'Age must be between 0 and 150'
        except (ValueError, TypeError):
            errors['age'] = 'Age must be a valid number'
    
    # 3. Phone number validation
    if 'phone' in data and data['phone']:
        phone_validator = RegexValidator(
            regex=r'^\+?1?\d{9,15}$',
            message="Phone number must be valid format (9-15 digits, optional +)"
        )
        try:
            phone_validator(str(data['phone']))
        except ValidationError:
            errors['phone'] = 'Invalid phone number format'
    
    # 4. Blood pressure validation (format: systolic/diastolic)
    if 'blood_pressure' in data and data['blood_pressure']:
        try:
            bp_str = str(data['blood_pressure'])
            if '/' in bp_str:
                sys, dia = map(int, bp_str.split('/'))
                if not (60 <= sys <= 250 and 40 <= dia <= 150):
                    errors['blood_pressure'] = 'Blood pressure values out of valid range (sys: 60-250, dia: 40-150)'
            else:
                errors['blood_pressure'] = 'Blood pressure must be in format: systolic/diastolic'
        except (ValueError, AttributeError):
            errors['blood_pressure'] = 'Invalid blood pressure format'
    
    # 5. Heart rate validation
    if 'heart_rate' in data and data['heart_rate'] is not None:
        try:
            hr = int(data['heart_rate'])
            if not (30 <= hr <= 250):
                errors['heart_rate'] = 'Heart rate must be between 30 and 250 bpm'
        except (ValueError, TypeError):
            errors['heart_rate'] = 'Heart rate must be a valid number'
    
    # 6. Temperature validation (Celsius)
    if 'temperature' in data and data['temperature'] is not None:
        try:
            temp = float(data['temperature'])
            if not (30.0 <= temp <= 45.0):
                errors['temperature'] = 'Temperature must be between 30.0 and 45.0 °C'
        except (ValueError, TypeError):
            errors['temperature'] = 'Temperature must be a valid number'
    
    # 7. Weight validation (kg)
    if 'weight' in data and data['weight'] is not None:
        try:
            weight = float(data['weight'])
            if not (0.5 <= weight <= 500.0):
                errors['weight'] = 'Weight must be between 0.5 and 500 kg'
        except (ValueError, TypeError):
            errors['weight'] = 'Weight must be a valid number'
    
    # 8. Height validation (cm)
    if 'height' in data and data['height'] is not None:
        try:
            height = float(data['height'])
            if not (20.0 <= height <= 300.0):
                errors['height'] = 'Height must be between 20 and 300 cm'
        except (ValueError, TypeError):
            errors['height'] = 'Height must be a valid number'
    
    # 9. Gender validation (allow-list)
    if 'gender' in data and data['gender']:
        valid_genders = ['M', 'F', 'Male', 'Female', 'Other', 'Prefer not to say']
        if data['gender'] not in valid_genders:
            errors['gender'] = f'Gender must be one of: {", ".join(valid_genders)}'
    
    # 10. String length validation for text fields
    text_fields = {
        'subject_initials': 10,
        'name': 200,
        'medical_history': 5000,
        'current_medications': 2000,
        'allergies': 1000,
        'diagnosis': 1000,
    }
    
    for field, max_length in text_fields.items():
        if field in data and data[field]:
            if len(str(data[field])) > max_length:
                errors[field] = f'{field} exceeds maximum length of {max_length} characters'
    
    return errors if errors else None


def validate_csv_export_data(data):
    """
    Validate CSV export request data.
    
    Args:
        data: Data to be exported (list or dict)
        
    Returns:
        dict or None: Error dict if validation fails, None if valid
    """
    if not isinstance(data, (list, dict)):
        return {'error': 'Data must be a list or dictionary'}
    
    if isinstance(data, list):
        # Prevent memory exhaustion with large datasets
        if len(data) > 10000:
            return {'error': 'Dataset too large (maximum 10,000 rows allowed)'}
        
        # Ensure all items are dictionaries
        if not all(isinstance(row, dict) for row in data):
            return {'error': 'All rows must be dictionary objects'}
        
        # Check if empty
        if len(data) == 0:
            return {'error': 'Cannot export empty dataset'}
    
    elif isinstance(data, dict):
        # If single dict, ensure it's not empty
        if not data:
            return {'error': 'Cannot export empty data'}
    
    return None


# Allow-list for file extensions in search
ALLOWED_FILE_EXTENSIONS = {
    '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.bmp',
    '.csv', '.xlsx', '.xls', '.txt', '.doc', '.docx',
    '.json', '.xml', '.zip', '.rar'
}


def validate_search_query(term, ext=None):
    """
    Validate search query parameters.
    
    Args:
        term (str): Search term
        ext (str, optional): File extension filter
        
    Returns:
        dict or None: Error dict if validation fails, None if valid
    """
    if not term:
        return {'error': 'Search term is required'}
    
    # Validate term length
    if len(term) < 2:
        return {'error': 'Search term too short (minimum 2 characters)'}
    
    if len(term) > 200:
        return {'error': 'Search term too long (maximum 200 characters)'}
    
    # Validate extension if provided
    if ext:
        # Normalize extension
        if not ext.startswith('.'):
            ext = f'.{ext}'
        
        if ext.lower() not in ALLOWED_FILE_EXTENSIONS:
            return {
                'error': f'Invalid file extension. Allowed: {", ".join(sorted(ALLOWED_FILE_EXTENSIONS))}'
            }
    
    return None
