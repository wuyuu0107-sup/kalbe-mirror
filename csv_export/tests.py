import json
import csv
from io import StringIO
from unittest.mock import patch, Mock
from django.test import TestCase, Client
from django.urls import reverse
from django.http import HttpResponse


class CSVExportTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = '/csv/export/' 
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

    # Happy Path Test
    @patch('csv_export.views.json_to_csv')
    def test_successful_csv_export_with_ocr_data(self, mock_json_to_csv):
        """Test successful CSV export with valid OCR medical data"""
        mock_json_to_csv.return_value = None
        
        response = self.client.post(
            self.url,
            data=json.dumps(self.valid_ocr_data),
            content_type='application/json'
        )
        
        # Check response status and headers
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertEqual(
            response['Content-Disposition'], 
            'attachment; filename="report.csv"'
        )
        
        # Verify json_to_csv was called with correct arguments
        mock_json_to_csv.assert_called_once()
        call_args = mock_json_to_csv.call_args
        self.assertEqual(call_args[0][0], self.valid_ocr_data)
        self.assertIsInstance(call_args[0][1], csv.writer)

    