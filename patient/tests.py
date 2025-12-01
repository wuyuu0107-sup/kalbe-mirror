from django.test import TestCase, Client
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse
from datetime import date
from decimal import Decimal
import json
from .models import Patient
from .utility.converters import (
    extract_result_value,
    parse_date_string,
    safe_float_conversion,
    safe_int_conversion
)
from .utility.field_extractors import (
    extract_demography_fields,
    extract_vital_signs_fields,
    extract_medical_history_fields,
    extract_lab_results_fields
)
from .utility.json_mapper import map_ocr_json_to_patient


class PatientModelTest(TestCase):
    
    def setUp(self):
        """Common valid patient data"""
        self.valid_data = {
            'subject_initials': 'TEST',
            'gender': 'Male',
            'date_of_birth': date(2000, 1, 1),
            'address': 'Test Address',
            'phone_number': '1234567890',
            'age': 25,
            'height': Decimal('170.00'),
            'weight': Decimal('70.00'),
            'bmi': Decimal('24.22'),
            'systolic': 120,
            'diastolic': 80,
            'smoking_habit': 'No',
            'smoker': 0,
            'drinking_habit': 'No',
            'hemoglobin': Decimal('15.00'),
            'random_blood_glucose': Decimal('90.00'),
            'sgot': Decimal('20.00'),
            'sgpt': Decimal('20.00'),
            'alkaline_phosphatase': Decimal('80.00')
        }
    
    def test_create_patient_with_all_fields(self):
        """Test creating a patient with all fields populated"""
        patient = Patient.objects.create(
            sin="14515",
            name="Yunus Saputra",
            **self.valid_data
        )
        
        self.assertEqual(patient.sin, "14515")
        self.assertEqual(patient.name, "Yunus Saputra")
        self.assertEqual(patient.subject_initials, "TEST")
    
    def test_create_patient_without_sin_and_name(self):
        """Test SIN and name are optional (can be None)"""
        patient = Patient.objects.create(**self.valid_data)
        
        self.assertIsNone(patient.sin)
        self.assertIsNone(patient.name)
    
    def test_create_patient_with_blank_sin_and_name(self):
        """Test SIN and name can be blank strings"""
        patient = Patient.objects.create(
            sin="",
            name="",
            **self.valid_data
        )
        
        self.assertEqual(patient.sin, "")
        self.assertEqual(patient.name, "")
    
    def test_patient_str_representation(self):
        """Test string representation returns subject initials"""
        patient = Patient.objects.create(**self.valid_data)
        self.assertEqual(str(patient), "TEST")
    
    def test_missing_subject_initials_saves_as_empty_string(self):
        """Test that missing subject_initials saves as empty string"""
        data = self.valid_data.copy()
        del data['subject_initials']
        
        patient = Patient.objects.create(**data)
        self.assertEqual(patient.subject_initials, '')

    def test_missing_gender_saves_as_null(self):
        """Test that missing gender saves as null"""
        data = self.valid_data.copy()
        del data['gender']
        
        patient = Patient.objects.create(**data)
        self.assertIsNone(patient.gender)
    
    def test_subject_initials_max_length(self):
        """Test subject_initials respects max_length of 10"""
        patient = Patient.objects.create(
            subject_initials="A" * 10,
            **{k: v for k, v in self.valid_data.items() if k != 'subject_initials'}
        )
        self.assertEqual(len(patient.subject_initials), 10)
    
    def test_sin_max_length(self):
        """Test SIN respects max_length of 50"""
        patient = Patient.objects.create(
            sin="1" * 50,
            **self.valid_data
        )
        self.assertEqual(len(patient.sin), 50)
    
    def test_decimal_field_precision_height(self):
        """Test height decimal precision (max_digits=5, decimal_places=2)"""
        patient = Patient.objects.create(
            height=Decimal("999.99"),
            **{k: v for k, v in self.valid_data.items() if k != 'height'}
        )
        self.assertEqual(patient.height, Decimal("999.99"))
    
    def test_decimal_field_precision_hemoglobin(self):
        """Test hemoglobin decimal precision (max_digits=4, decimal_places=2)"""
        patient = Patient.objects.create(
            hemoglobin=Decimal("99.99"),
            **{k: v for k, v in self.valid_data.items() if k != 'hemoglobin'}
        )
        self.assertEqual(patient.hemoglobin, Decimal("99.99"))
    
    def test_negative_age(self):
        """Test that negative age is saved (no validation at model level)"""
        patient = Patient.objects.create(
            age=-5,
            **{k: v for k, v in self.valid_data.items() if k != 'age'}
        )
        self.assertEqual(patient.age, -5)
    
    def test_zero_values_for_measurements(self):
        """Test zero values are accepted for measurements"""
        patient = Patient.objects.create(
            height=Decimal("0.00"),
            weight=Decimal("0.00"),
            bmi=Decimal("0.00"),
            **{k: v for k, v in self.valid_data.items() 
               if k not in ['height', 'weight', 'bmi']}
        )
        self.assertEqual(patient.height, Decimal("0.00"))
        self.assertEqual(patient.weight, Decimal("0.00"))
    
    def test_smoker_as_integer(self):
        """Test smoker field accepts integer values"""
        patient = Patient.objects.create(
            smoker=5,
            **{k: v for k, v in self.valid_data.items() if k != 'smoker'}
        )
        self.assertEqual(patient.smoker, 5)
    
    def test_patient_retrieval(self):
        """Test patient can be retrieved after creation"""
        Patient.objects.create(
            sin="12345",
            **self.valid_data
        )
        
        patient = Patient.objects.get(sin="12345")
        self.assertEqual(patient.subject_initials, "TEST")
    
    def test_multiple_patients_creation(self):
        """Test creating multiple patients"""
        Patient.objects.create(
            subject_initials="PAT1",
            **{k: v for k, v in self.valid_data.items() if k != 'subject_initials'}
        )
        Patient.objects.create(
            subject_initials="PAT2",
            **{k: v for k, v in self.valid_data.items() if k != 'subject_initials'}
        )
        
        self.assertEqual(Patient.objects.count(), 2)


# ============ CONVERTER TESTS ============
class ConvertersTest(TestCase):
    
    def test_extract_result_value_with_hasil_dict(self):
        """Test extracting 'Hasil' from nested dictionary"""
        field_data = {'Hasil': '15.5', 'unit': 'g/dL'}
        self.assertEqual(extract_result_value(field_data), '15.5')
    
    def test_extract_result_value_with_plain_value(self):
        """Test extracting plain value"""
        self.assertEqual(extract_result_value('15.5'), '15.5')
        self.assertEqual(extract_result_value(15.5), 15.5)
    
    def test_extract_result_value_with_none(self):
        """Test extracting None"""
        self.assertIsNone(extract_result_value(None))
    
    def test_parse_date_string_dd_mmm_yyyy(self):
        """Test parsing date in DD/MMM/YYYY format"""
        result = parse_date_string('16/Jul/1999')
        self.assertEqual(result, date(1999, 7, 16))
    
    def test_parse_date_string_dd_mm_yyyy(self):
        """Test parsing date in DD/MM/YYYY format"""
        result = parse_date_string('16/07/1999')
        self.assertEqual(result, date(1999, 7, 16))
    
    def test_parse_date_string_invalid_format(self):
        """Test parsing invalid date format returns None"""
        self.assertIsNone(parse_date_string('1999-07-16'))
        self.assertIsNone(parse_date_string('invalid'))
    
    def test_parse_date_string_empty(self):
        """Test parsing empty/None date returns None"""
        self.assertIsNone(parse_date_string(''))
        self.assertIsNone(parse_date_string(None))
    
    def test_safe_float_conversion_valid(self):
        """Test converting valid values to float"""
        self.assertEqual(safe_float_conversion('15.5'), 15.5)
        self.assertEqual(safe_float_conversion(15), 15.0)
        self.assertEqual(safe_float_conversion('100'), 100.0)
    
    def test_safe_float_conversion_invalid(self):
        """Test converting invalid values returns default"""
        self.assertIsNone(safe_float_conversion('invalid'))
        self.assertIsNone(safe_float_conversion(None))
        self.assertIsNone(safe_float_conversion(''))
    
    def test_safe_float_conversion_custom_default(self):
        """Test converting invalid values with custom default"""
        self.assertEqual(safe_float_conversion('invalid', default=0.0), 0.0)
        self.assertEqual(safe_float_conversion(None, default=-1.0), -1.0)
    
    def test_safe_int_conversion_valid(self):
        """Test converting valid values to int"""
        self.assertEqual(safe_int_conversion('25'), 25)
        self.assertEqual(safe_int_conversion(25.7), 25)
        self.assertEqual(safe_int_conversion('100.5'), 100)
    
    def test_safe_int_conversion_invalid(self):
        """Test converting invalid values returns default"""
        self.assertIsNone(safe_int_conversion('invalid'))
        self.assertIsNone(safe_int_conversion(None))
        self.assertIsNone(safe_int_conversion(''))
    
    def test_safe_int_conversion_custom_default(self):
        """Test converting invalid values with custom default"""
        self.assertEqual(safe_int_conversion('invalid', default=0), 0)
        self.assertEqual(safe_int_conversion(None, default=-1), -1)


# ============ FIELD EXTRACTOR TESTS ============
class FieldExtractorsTest(TestCase):
    
    def test_extract_demography_fields_complete(self):
        """Test extracting all demographic fields"""
        demography = {
            'sin': '14515',
            'name': 'Yunus Saputra',
            'subject_initials': 'YSSA',
            'gender': 'Male',
            'date_of_birth': '16/07/1999',
            'address': 'Johar Baru',
            'phone_number': '85936644050',
            'age': '25',
            'height_cm': '175',
            'weight_kg': '70',
            'bmi': '22.86'
        }
        
        result = extract_demography_fields(demography)
        
        self.assertEqual(result['sin'], '14515')
        self.assertEqual(result['name'], 'Yunus Saputra')
        self.assertEqual(result['subject_initials'], 'YSSA')
        self.assertEqual(result['gender'], 'Male')
        self.assertEqual(result['date_of_birth'], date(1999, 7, 16))
        self.assertEqual(result['age'], 25)
        self.assertEqual(result['height'], 175.0)
        self.assertEqual(result['weight'], 70.0)
        self.assertEqual(result['bmi'], 22.86)
    
    def test_extract_demography_fields_partial(self):
        """Test extracting with missing optional fields"""
        demography = {
            'subject_initials': 'TEST',
            'gender': 'Female',
            'age': '30'
        }
        
        result = extract_demography_fields(demography)
        
        self.assertIsNone(result['sin'])
        self.assertIsNone(result['name'])
        self.assertEqual(result['subject_initials'], 'TEST')
        self.assertEqual(result['address'], '')
        self.assertEqual(result['phone_number'], '')
    
    def test_extract_vital_signs_fields_complete(self):
        """Test extracting vital signs"""
        vital_signs = {
            'systolic_bp': '120',
            'diastolic_bp': '80'
        }
        
        result = extract_vital_signs_fields(vital_signs)
        
        self.assertEqual(result['systolic'], 120)
        self.assertEqual(result['diastolic'], 80)
    
    def test_extract_vital_signs_fields_missing(self):
        """Test extracting vital signs with missing data"""
        vital_signs = {}
        
        result = extract_vital_signs_fields(vital_signs)
        
        self.assertIsNone(result['systolic'])
        self.assertIsNone(result['diastolic'])
    
    def test_extract_medical_history_fields_complete(self):
        """Test extracting medical history"""
        medical_history = {
            'smoking_habit': 'Yes',
            'smoker_cigarettes_per_day': '5',
            'drinking_habit': 'No'
        }
        
        result = extract_medical_history_fields(medical_history)
        
        self.assertEqual(result['smoking_habit'], 'Yes')
        self.assertEqual(result['smoker'], 5)
        self.assertEqual(result['drinking_habit'], 'No')
    
    def test_extract_medical_history_fields_defaults(self):
        """Test extracting medical history with missing data"""
        medical_history = {}
        
        result = extract_medical_history_fields(medical_history)
        
        self.assertEqual(result['smoking_habit'], '')
        self.assertEqual(result['smoker'], 0)
        self.assertEqual(result['drinking_habit'], '')
    
    def test_extract_lab_results_fields_complete(self):
        """Test extracting lab results with nested Hasil"""
        hematology = {
            'hemoglobin': {'Hasil': '15.5', 'unit': 'g/dL'}
        }
        clinical_chemistry = {
            'random_blood_glucose': {'Hasil': '90', 'unit': 'mg/dL'},
            'sgot': {'Hasil': '20'},
            'sgpt': {'Hasil': '22'},
            'alkaline_phosphatase': {'Hasil': '85'}
        }
        
        result = extract_lab_results_fields(hematology, clinical_chemistry)
        
        self.assertEqual(result['hemoglobin'], 15.5)
        self.assertEqual(result['random_blood_glucose'], 90.0)
        self.assertEqual(result['sgot'], 20.0)
        self.assertEqual(result['sgpt'], 22.0)
        self.assertEqual(result['alkaline_phosphatase'], 85.0)
    
    def test_extract_lab_results_fields_plain_values(self):
        """Test extracting lab results with plain values"""
        hematology = {'hemoglobin': '14.2'}
        clinical_chemistry = {
            'random_blood_glucose': '95',
            'sgot': '18',
            'sgpt': '20',
            'alkaline_phosphatase': '80'
        }
        
        result = extract_lab_results_fields(hematology, clinical_chemistry)
        
        self.assertEqual(result['hemoglobin'], 14.2)
        self.assertEqual(result['random_blood_glucose'], 95.0)
    
    def test_extract_lab_results_fields_missing(self):
        """Test extracting lab results with missing data"""
        hematology = {}
        clinical_chemistry = {}
        
        result = extract_lab_results_fields(hematology, clinical_chemistry)
        
        self.assertIsNone(result['hemoglobin'])
        self.assertIsNone(result['random_blood_glucose'])
        self.assertIsNone(result['sgot'])
        self.assertIsNone(result['sgpt'])
        self.assertIsNone(result['alkaline_phosphatase'])


# ============ JSON MAPPER TESTS ============
class JsonMapperTest(TestCase):
    
    def test_map_ocr_json_complete_data(self):
        """Test mapping complete OCR JSON to patient data"""
        json_data = {
            'DEMOGRAPHY': {
                'sin': '14515',
                'name': 'Yunus Saputra',
                'subject_initials': 'YSSA',
                'gender': 'Male',
                'date_of_birth': '16/07/1999',
                'address': 'Johar Baru',
                'phone_number': '85936644050',
                'age': '25',
                'height_cm': '175',
                'weight_kg': '70',
                'bmi': '22.86'
            },
            'VITAL_SIGNS': {
                'systolic_bp': '120',
                'diastolic_bp': '80'
            },
            'MEDICAL_HISTORY': {
                'smoking_habit': 'Yes',
                'smoker_cigarettes_per_day': '5',
                'drinking_habit': 'No'
            },
            'HEMATOLOGY': {
                'hemoglobin': {'Hasil': '15.5'}
            },
            'CLINICAL_CHEMISTRY': {
                'random_blood_glucose': {'Hasil': '90'},
                'sgot': {'Hasil': '20'},
                'sgpt': {'Hasil': '22'},
                'alkaline_phosphatase': {'Hasil': '85'}
            }
        }
        
        result = map_ocr_json_to_patient(json_data)
        
        self.assertEqual(result['sin'], '14515')
        self.assertEqual(result['subject_initials'], 'YSSA')
        self.assertEqual(result['age'], 25)
        self.assertEqual(result['systolic'], 120)
        self.assertEqual(result['hemoglobin'], 15.5)
    
    def test_map_ocr_json_empty_sections(self):
        """Test mapping with empty sections"""
        json_data = {
            'DEMOGRAPHY': {},
            'VITAL_SIGNS': {},
            'MEDICAL_HISTORY': {},
            'HEMATOLOGY': {},
            'CLINICAL_CHEMISTRY': {}
        }
        
        result = map_ocr_json_to_patient(json_data)
        
        self.assertIsNone(result['sin'])
        self.assertIsNone(result['systolic'])
        self.assertEqual(result['smoker'], 0)
    
    def test_map_ocr_json_missing_sections(self):
        """Test mapping with missing sections"""
        json_data = {}
        
        result = map_ocr_json_to_patient(json_data)
        
        self.assertIsNone(result['sin'])
        self.assertIsNone(result['hemoglobin'])


# ============ VIEW TESTS ============
class CreatePatientViewTest(TestCase):
    
    def setUp(self):
        self.client = Client()
        self.url = '/patient/create/'
        self.valid_data = {
            'DEMOGRAPHY': {
                'subject_initials': 'TEST',
                'gender': 'Male',
                'date_of_birth': '01/01/2000',
                'address': 'Test Address',
                'phone_number': '1234567890',
                'age': '25',
                'height_cm': '170',
                'weight_kg': '70',
                'bmi': '24.22'
            },
            'VITAL_SIGNS': {
                'systolic_bp': '120',
                'diastolic_bp': '80'
            },
            'MEDICAL_HISTORY': {
                'smoking_habit': 'No',
                'smoker_cigarettes_per_day': '0',
                'drinking_habit': 'No'
            },
            'HEMATOLOGY': {
                'hemoglobin': {'Hasil': '15'}
            },
            'CLINICAL_CHEMISTRY': {
                'random_blood_glucose': {'Hasil': '90'},
                'sgot': {'Hasil': '20'},
                'sgpt': {'Hasil': '20'},
                'alkaline_phosphatase': {'Hasil': '80'}
            }
        }
    
    def test_create_patient_success(self):
        """Test successful patient creation"""
        response = self.client.post(
            self.url,
            data=json.dumps(self.valid_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('patient_id', data)
        self.assertEqual(data['patient']['subject_initials'], 'TEST')
        
        # Verify patient was created in DB
        self.assertEqual(Patient.objects.count(), 1)
        patient = Patient.objects.first()
        self.assertEqual(patient.subject_initials, 'TEST')
    
    def test_create_patient_invalid_json(self):
        """Test with invalid JSON format"""
        response = self.client.post(
            self.url,
            data='invalid json',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Invalid JSON format')
    
    def test_create_patient_missing_required_fields(self):
        """Test with missing required fields"""
        incomplete_data = {'DEMOGRAPHY': {}}
        
        response = self.client.post(
            self.url,
            data=json.dumps(incomplete_data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Failed to create patient')
    
    def test_create_patient_get_method_not_allowed(self):
        """Test that GET method is not allowed"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 405)
    
    def test_create_patient_with_optional_fields_empty(self):
        """Test creating patient with optional SIN and name empty"""
        data = self.valid_data.copy()
        data['DEMOGRAPHY']['sin'] = None
        data['DEMOGRAPHY']['name'] = None
        
        response = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 201)
        patient = Patient.objects.first()
        self.assertIsNone(patient.sin)
        self.assertIsNone(patient.name)