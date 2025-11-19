from django.test import TestCase
from django.core.exceptions import ValidationError
from datetime import date
from decimal import Decimal
from .models import Patient


class PatientModelTest(TestCase):
    
    def test_create_patient_with_all_fields(self):
        """Test creating a patient with all fields populated"""
        patient = Patient.objects.create(
            sin="14515",
            name="Yunus Saputra",
            subject_initials="YSSA",
            gender="Male",
            date_of_birth=date(1999, 7, 16),
            address="Johar Baru",
            phone_number="85936644050",
            age=25,
            height=Decimal("175.00"),
            weight=Decimal("70.00"),
            bmi=Decimal("22.86"),
            systolic=121,
            diastolic=75,
            smoking_habit="Yes",
            smoker=5,
            drinking_habit="No",
            hemoglobin=Decimal("16.50"),
            random_blood_glucose=Decimal("84.00"),
            sgot=Decimal("13.00"),
            sgpt=Decimal("13.00"),
            alkaline_phosphatase=Decimal("91.00")
        )
        
        self.assertEqual(patient.sin, "14515")
        self.assertEqual(patient.name, "Yunus Saputra")
        self.assertEqual(patient.subject_initials, "YSSA")
        self.assertEqual(patient.age, 25)
    
    def test_create_patient_without_sin_and_name(self):
        """Test creating a patient without SIN and name (optional fields)"""
        patient = Patient.objects.create(
            sin=None,
            name=None,
            subject_initials="RDHO",
            gender="Male",
            date_of_birth=date(2005, 5, 10),
            address="Kampung Pulo",
            phone_number="858000000000",
            age=20,
            height=Decimal("180.00"),
            weight=Decimal("65.00"),
            bmi=Decimal("20.06"),
            systolic=111,
            diastolic=76,
            smoking_habit="Yes",
            smoker=6,
            drinking_habit="No",
            hemoglobin=Decimal("13.00"),
            random_blood_glucose=Decimal("84.00"),
            sgot=Decimal("13.00"),
            sgpt=Decimal("9.00"),
            alkaline_phosphatase=Decimal("79.00")
        )
        
        self.assertIsNone(patient.sin)
        self.assertIsNone(patient.name)
        self.assertEqual(patient.subject_initials, "RDHO")
    
    def test_patient_str_representation(self):
        """Test string representation returns subject initials"""
        patient = Patient.objects.create(
            subject_initials="TEST",
            gender="Male",
            date_of_birth=date(2000, 1, 1),
            address="Test Address",
            phone_number="1234567890",
            age=25,
            height=Decimal("170.00"),
            weight=Decimal("70.00"),
            bmi=Decimal("24.22"),
            systolic=120,
            diastolic=80,
            smoking_habit="No",
            smoker=0,
            drinking_habit="No",
            hemoglobin=Decimal("15.00"),
            random_blood_glucose=Decimal("90.00"),
            sgot=Decimal("20.00"),
            sgpt=Decimal("20.00"),
            alkaline_phosphatase=Decimal("80.00")
        )
        
        self.assertEqual(str(patient), "TEST")
    
    def test_patient_fields_are_saved_correctly(self):
        """Test that all patient fields are saved and retrieved correctly"""
        patient = Patient.objects.create(
            sin="12345",
            name="Test Patient",
            subject_initials="TPAT",
            gender="Female",
            date_of_birth=date(1995, 3, 15),
            address="Test District",
            phone_number="081234567890",
            age=30,
            height=Decimal("165.00"),
            weight=Decimal("60.00"),
            bmi=Decimal("22.04"),
            systolic=115,
            diastolic=70,
            smoking_habit="No",
            smoker=0,
            drinking_habit="Occasional",
            hemoglobin=Decimal("14.50"),
            random_blood_glucose=Decimal("95.00"),
            sgot=Decimal("25.00"),
            sgpt=Decimal("22.00"),
            alkaline_phosphatase=Decimal("85.00")
        )
        
        retrieved_patient = Patient.objects.get(subject_initials="TPAT")
        
        self.assertEqual(retrieved_patient.gender, "Female")
        self.assertEqual(retrieved_patient.height, Decimal("165.00"))
        self.assertEqual(retrieved_patient.smoker, 0)
        self.assertEqual(retrieved_patient.drinking_habit, "Occasional")