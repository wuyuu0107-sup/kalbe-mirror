from datetime import datetime


def extract_result_value(field_data):
    """
    Extracts 'Hasil' value from nested lab result dictionary.
    
    Args:
        field_data: Either a dict with 'Hasil' key or a plain value
        
    Returns:
        The 'Hasil' value if dict, otherwise the original value
    """
    if isinstance(field_data, dict) and 'Hasil' in field_data:
        return field_data['Hasil']
    return field_data


def parse_date_string(date_str):
    """
    Parses date from DD/MMM/YYYY or DD/MM/YYYY format.
    
    Args:
        date_str: Date string to parse
        
    Returns:
        date object or None if parsing fails
    """
    if not date_str:
        return None
    try:
        # Try DD/MMM/YYYY format first (e.g., "01/FEB/2003")
        return datetime.strptime(date_str, '%d/%b/%Y').date()
    except ValueError:
        try:
            # Try DD/MM/YYYY format
            return datetime.strptime(date_str, '%d/%m/%Y').date()
        except ValueError:
            return None


def safe_float_conversion(value, default=None):
    """
    Safely converts value to float.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Float value or default
    """
    if value is None or value == '':
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int_conversion(value, default=None):
    """
    Safely converts value to integer.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Integer value or default
    """
    if value is None or value == '':
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default

