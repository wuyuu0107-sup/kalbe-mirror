from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from typing import Dict, Any

from ocr.utils.normalization import (
    normalize_payload,
    _normalize_section_keys,
    _process_demography,
    _process_vital_signs,
    _process_serology,
    _process_measurement_sections,
    _collect_extra_sections,
    _build_ordered_output
)


class OCRTests(TestCase):
    def test_missing_file_returns_error(self):
        # view returns JSON with success False and an error message when pdf or API key missing
        resp = self.client.post("/ocr/", {})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, dict)
        self.assertIn("success", data)
        self.assertFalse(data["success"])
        self.assertIn("error", data)


    def test_pdf_support_missing_returns_error(self):
        # If the system doesn't have PyMuPDF or API key, posting a PDF without API key yields error
        fake_pdf = b"%PDF-1.4\n%EOF\n"
        uploaded = SimpleUploadedFile("test.pdf", fake_pdf, content_type="application/pdf")
        resp = self.client.post("/ocr/", {"pdf": uploaded})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("success", data)
        self.assertFalse(data["success"])
        self.assertIn("error", data)

class NormalizePayloadTests(TestCase):
    
    def test_non_dict_input_returns_default_schema(self):
        result = normalize_payload(None)
        self.assertIn("DEMOGRAPHY", result)
        self.assertIn("MEDICAL_HISTORY", result)
        self.assertIn("VITAL_SIGNS", result)
        self.assertEqual(result["DEMOGRAPHY"]["age"], None)
    
    def test_empty_dict_returns_default_schema(self):
        result = normalize_payload({})
        self.assertIn("DEMOGRAPHY", result)
        self.assertIsNone(result["DEMOGRAPHY"]["subject_initials"])
    
    def test_section_order_is_correct(self):
        result = normalize_payload({})
        keys = list(result.keys())
        expected_order = [
            "DEMOGRAPHY", "MEDICAL_HISTORY", "VITAL_SIGNS",
            "SEROLOGY", "URINALYSIS", "HEMATOLOGY", "CLINICAL_CHEMISTRY"
        ]
        self.assertEqual(keys[:7], expected_order)
    
    def test_demography_age_converted_to_int(self):
        data = {"DEMOGRAPHY": {"age": "25"}}
        result = normalize_payload(data)
        self.assertEqual(result["DEMOGRAPHY"]["age"], 25)
        self.assertIsInstance(result["DEMOGRAPHY"]["age"], int)
    
    def test_demography_age_invalid_becomes_none(self):
        data = {"DEMOGRAPHY": {"age": "invalid"}}
        result = normalize_payload(data)
        self.assertIsNone(result["DEMOGRAPHY"]["age"])
    
    def test_demography_weight_height_bmi_are_strings(self):
        data = {"DEMOGRAPHY": {"weight_kg": 70.5, "height_cm": 175, "bmi": 23.0}}
        result = normalize_payload(data)
        self.assertEqual(result["DEMOGRAPHY"]["weight_kg"], "70.5")
        self.assertEqual(result["DEMOGRAPHY"]["height_cm"], "175")
        self.assertEqual(result["DEMOGRAPHY"]["bmi"], "23.0")
    
    def test_vital_signs_converted_to_strings(self):
        data = {"VITAL_SIGNS": {"systolic_bp": 120, "diastolic_bp": 80, "heart_rate": 72}}
        result = normalize_payload(data)
        self.assertEqual(result["VITAL_SIGNS"]["systolic_bp"], "120")
        self.assertEqual(result["VITAL_SIGNS"]["diastolic_bp"], "80")
        self.assertEqual(result["VITAL_SIGNS"]["heart_rate"], "72")
    
    def test_serology_dict_values_extracted_to_strings(self):
        data = {"SEROLOGY": {"hbsag": {"Hasil": "Negative"}, "hcv": "Negative"}}
        result = normalize_payload(data)
        self.assertEqual(result["SEROLOGY"]["hbsag"], "Negative")
        self.assertEqual(result["SEROLOGY"]["hcv"], "Negative")
    
    def test_urinalysis_has_4_key_structure(self):
        data = {"URINALYSIS": {"ph": {"Hasil": "6.5"}}}
        result = normalize_payload(data)
        self.assertIn("Hasil", result["URINALYSIS"]["ph"])
        self.assertIn("Nilai Rujukan", result["URINALYSIS"]["ph"])
        self.assertIn("Satuan", result["URINALYSIS"]["ph"])
        self.assertIn("Metode", result["URINALYSIS"]["ph"])
    
    def test_urinalysis_default_method_is_carik_celup(self):
        data = {"URINALYSIS": {"ph": {}}}
        result = normalize_payload(data)
        self.assertEqual(result["URINALYSIS"]["ph"]["Metode"], "Carik Celup")
    
    def test_extra_sections_appended_at_end(self):
        data = {"UNKNOWN_SECTION": {"key": "value"}}
        result = normalize_payload(data)
        self.assertIn("UNKNOWN_SECTION", result)
        keys = list(result.keys())
        self.assertGreater(keys.index("UNKNOWN_SECTION"), 6)


class NormalizeSectionKeysTests(TestCase):
    
    def test_uppercase_section_keys(self):
        extracted = {"demography": {"age": 25}, "vital signs": {"systolic_bp": 120}}
        result = _normalize_section_keys(extracted)
        self.assertIn("DEMOGRAPHY", result)
        self.assertIn("VITAL_SIGNS", result)
    
    def test_unknown_keys_preserved(self):
        extracted = {"CUSTOM_SECTION": {"data": "value"}}
        result = _normalize_section_keys(extracted)
        self.assertIn("CUSTOM_SECTION", result)


class ProcessDemographyTests(TestCase):
    
    def test_age_converted_to_int(self):
        demo = {"age": "30"}
        _process_demography(demo)
        self.assertEqual(demo["age"], 30)
    
    def test_invalid_age_becomes_none(self):
        demo = {"age": "not_a_number"}
        _process_demography(demo)
        self.assertIsNone(demo["age"])
    
    def test_weight_height_bmi_converted_to_strings(self):
        demo = {"weight_kg": 65, "height_cm": 170, "bmi": 22.5}
        _process_demography(demo)
        self.assertEqual(demo["weight_kg"], "65")
        self.assertEqual(demo["height_cm"], "170")
        self.assertEqual(demo["bmi"], "22.5")


class ProcessVitalSignsTests(TestCase):
    
    def test_vitals_converted_to_strings(self):
        vitals = {"systolic_bp": 110, "diastolic_bp": 70, "heart_rate": 65}
        _process_vital_signs(vitals)
        self.assertEqual(vitals["systolic_bp"], "110")
        self.assertEqual(vitals["diastolic_bp"], "70")
        self.assertEqual(vitals["heart_rate"], "65")
    
    def test_none_values_stay_none(self):
        vitals = {"systolic_bp": None}
        _process_vital_signs(vitals)
        self.assertIsNone(vitals["systolic_bp"])


class ProcessSerologyTests(TestCase):
    
    def test_dict_with_hasil_extracted(self):
        serology = {"hbsag": {"Hasil": "Negative"}}
        base = {"hbsag": None, "hcv": None, "hiv": None}
        _process_serology(serology, base)
        self.assertEqual(base["hbsag"], "Negative")
    
    def test_string_value_preserved(self):
        serology = {"hcv": "Negative"}
        base = {"hbsag": None, "hcv": None, "hiv": None}
        _process_serology(serology, base)
        self.assertEqual(base["hcv"], "Negative")


class CollectExtraSectionsTests(TestCase):
    
    def test_known_sections_excluded(self):
        norm = {
            "DEMOGRAPHY": {},
            "MEDICAL_HISTORY": {},
            "CUSTOM_SECTION": {"data": "value"}
        }
        extras = _collect_extra_sections(norm)
        self.assertIn("CUSTOM_SECTION", extras)
        self.assertNotIn("DEMOGRAPHY", extras)
    
    def test_empty_when_no_extras(self):
        norm = {"DEMOGRAPHY": {}, "MEDICAL_HISTORY": {}}
        extras = _collect_extra_sections(norm)
        self.assertEqual(extras, {})