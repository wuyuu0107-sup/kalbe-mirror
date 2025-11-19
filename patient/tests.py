from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from datetime import date
from decimal import Decimal
from .models import Patient


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

    def test_missing_gender_saves_as_empty_string(self):
        """Test that missing gender saves as empty string"""
        data = self.valid_data.copy()
        del data['gender']
        
        patient = Patient.objects.create(**data)
        self.assertEqual(patient.gender, '')
    
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