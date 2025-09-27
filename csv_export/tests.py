import json
import csv
from io import StringIO
from django.test import TestCase, Client
from django.urls import reverse


class CSVExportTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.valid_ocr_data = {
            "DEMOGRAPHY": {
                "subject_initials": "LMNO",
                "sin": "76543",
                "study_drug": "Amlodipine Besylate 10 mg",
                "screening_date": "12/MAR/2024",
                "gender": "Male",
                "date_of_birth": "01/MEI/1999",
                "age": 25,
                "weight_kg": "48",
                "height_cm": "166",
                "bmi": "21"
            },
            "MEDICAL_HISTORY": {
                "smoker_cigarettes_per_day": None
            },
            "VITAL_SIGNS": {
                "systolic_bp": "108",
                "diastolic_bp": "77",
                "heart_rate": "85"
            },
            "SEROLOGY": {
                "hbsag": "Negative",
                "hcv": "Negative",
                "hiv": "Negative"
            },
            "URINALYSIS": {
                "ph": [8, "4-8", None, "Carik Celup"],
                "density": 1.039,
                "glucose": "(-)",
                "ketone": "(-)",
                "urobilinogen": "(-)",
                "bilirubin": "(-)",
                "blood": "(-)",
                "leucocyte_esterase": "(-)",
                "nitrite": "(-)"
            },
            "HEMATOLOGY": {
                "hemoglobin": [11, "10-25", "g/dL", "Reflectance Photomtr"],
                "hematocrit": 33,
                "leukocyte": 7,
                "erythrocyte": 70,
                "thrombocyte": 183,
                "esr": 10
            },
            "CLINICAL_CHEMISTRY": {
                "bilirubin_total": None,
                "alkaline_phosphatase": None,
                "sgot": 20,
                "sgpt": 21,
                "ureum": 19,
                "creatinine": 0.89,
                "random_blood_glucose": 122
            }
        }
