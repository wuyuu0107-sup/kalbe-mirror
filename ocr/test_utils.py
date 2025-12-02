from django.test import TestCase
from types import SimpleNamespace
import json

from ocr.utils.normalization import (
    normalize_payload,
    _normalize_section_keys,
    _process_demography,
    _process_vital_signs,
    _process_serology,
    _collect_extra_sections,
    _norm_date,
    _as_meas,
    _ensure_section,
    _to_str,
    _meas_template,
    _serology_str,
)
from ocr.utils.response_builders import build_success_response, build_error_response
from ocr.utils.spellchecker import correct_word
from annotation.models import Document  # ⬅️ no Patient import


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
    
    def test_process_serology_non_dict_does_nothing(self):
        """Cover early-return branch when serology is not a dict."""
        base = {"hbsag": "original"}
        _process_serology("not-a-dict", base)
        # base should be untouched
        self.assertEqual(base["hbsag"], "original")

class SerologyStrTests(TestCase):

    def test_serology_str_dict_without_known_keys(self):
        """Cover branch where dict has no Hasil/value/result keys."""
        data = {"foo": "bar"}
        result = _serology_str(data)
        # Should just be the stringified dict
        self.assertEqual(result, str(data))




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


class NormalizationHelpersTests(TestCase):
    
    def test_norm_date_handles_none(self):
        result = _norm_date(None)
        self.assertIsNone(result)
    
    def test_norm_date_handles_empty_string(self):
        result = _norm_date("")
        self.assertIsNone(result)
    
    def test_norm_date_converts_int_to_string(self):
        result = _norm_date(20240101)
        self.assertIsInstance(result, str)
    
    def test_norm_date_preserves_correct_format(self):
        result = _norm_date("13/APR/2024")
        self.assertEqual(result, "13/APR/2024")
    
    def test_norm_date_converts_slash_format(self):
        result = _norm_date("13/04/2024")
        self.assertEqual(result, "13/APR/2024")
    
    def test_norm_date_converts_dash_format(self):
        result = _norm_date("2024-04-13")
        self.assertEqual(result, "13/APR/2024")
    
    def test_norm_date_returns_original_for_invalid(self):
        result = _norm_date("invalid-date")
        self.assertEqual(result, "invalid-date")
    
    def test_as_meas_with_dict_input(self):
        val = {"Hasil": "6.5", "Satuan": "mg/dL"}
        result = _as_meas(val)
        
        self.assertEqual(result["Hasil"], "6.5")
        self.assertEqual(result["Satuan"], "mg/dL")
        self.assertIsNone(result["Nilai Rujukan"])
    
    def test_as_meas_with_scalar_value(self):
        result = _as_meas(7.2)
        
        self.assertEqual(result["Hasil"], "7.2")
        self.assertIsNone(result["Nilai Rujukan"])
    
    def test_as_meas_with_default_method(self):
        result = _as_meas({"Hasil": "6.5"}, default_method="Carik Celup")
        
        self.assertEqual(result["Metode"], "Carik Celup")
    
    def test_as_meas_preserves_extra_keys(self):
        val = {"Hasil": "6.5", "extra_key": "extra_value"}
        result = _as_meas(val)
        
        self.assertEqual(result["extra_key"], "extra_value")
    
    def test_ensure_section_transforms_all_fields(self):
        obj = {"ph": {"Hasil": "6.5"}, "glucose": "Negative"}
        fields = ["ph", "glucose"]
        
        _ensure_section(obj, fields)
        
        self.assertIn("Metode", obj["ph"])
        self.assertIn("Metode", obj["glucose"])
    
    def test_to_str_handles_none(self):
        result = _to_str(None)
        self.assertIsNone(result)
    
    def test_to_str_converts_number(self):
        result = _to_str(123)
        self.assertEqual(result, "123")
    
    def test_meas_template_has_all_keys(self):
        result = _meas_template()
        
        self.assertIn("Hasil", result)
        self.assertIn("Nilai Rujukan", result)
        self.assertIn("Satuan", result)
        self.assertIn("Metode", result)
        self.assertIsNone(result["Hasil"])
    
    def test_norm_date_with_lowercase_month_already_formatted(self):
        result = _norm_date("13/apr/2024")
        self.assertEqual(result, "13/APR/2024")
    
    def test_norm_date_mixed_case_month_already_formatted(self):
        result = _norm_date("01/Jan/2024")
        self.assertEqual(result, "01/JAN/2024")


class ResponseBuildersTests(TestCase):
    
    def test_success_response_contains_required_fields(self):
        doc = Document.objects.create(source="pdf", content_url="http://test.pdf")

        # Fake patient object – doesn’t depend on concrete Patient model
        pat = SimpleNamespace(id=1, name="Test", external_id="TEST-1")

        ordered_data = {"DEMOGRAPHY": {"age": 25}}
        extracted_data = {"processing_time": 1.5, "raw_text": "raw"}
        supabase_urls = {"json_url": "http://test.json"}
        
        response = build_success_response(doc, pat, ordered_data, extracted_data, supabase_urls)
        
        data = json.loads(response.content)
        self.assertTrue(data["success"])
        self.assertIsNone(data["error"])
        self.assertEqual(data["document_id"], doc.id)
        self.assertEqual(data["patient_id"], pat.id)
        self.assertEqual(data["processing_time"], 1.5)
        self.assertEqual(data["raw_response"], "raw")
        self.assertEqual(data["storage_json_url"], "http://test.json")
    
    def test_error_response_has_correct_structure(self):
        response = build_error_response("Test error")
        
        data = json.loads(response.content)
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Test error")
        self.assertEqual(data["processing_time"], 0)
        self.assertEqual(data["structured_data"], {})
        self.assertEqual(data["raw_response"], "")
    
    def test_error_response_status_code(self):
        response = build_error_response("Test error")
        
        self.assertEqual(response.status_code, 200)


class SpellcheckerTests(TestCase):
    
    def test_correct_word_ignores_single_letters(self):
        result = correct_word("a")
        self.assertEqual(result, "a")
    
    def test_correct_word_ignores_numbers(self):
        result = correct_word("123")
        self.assertEqual(result, "123")
    
    def test_correct_word_corrects_misspelling(self):
        result = correct_word("speling")
        self.assertEqual(result, "spelling")
    
    def test_correct_word_preserves_capitalization(self):
        result = correct_word("Speling")
        self.assertEqual(result, "Spelling")
    
    def test_correct_word_preserves_correct_spelling(self):
        result = correct_word("correct")
        self.assertEqual(result, "correct")
    
    def test_correct_word_handles_unknown_words(self):
        result = correct_word("xyzabc")
        self.assertIsInstance(result, str)


class ProcessMeasurementSectionsTests(TestCase):
    
    def test_process_measurement_sections_updates_base(self):
        from ocr.utils.normalization import _process_measurement_sections, _default_payload, URINALYSIS_FIELDS
        
        norm = {
            "URINALYSIS": {
                "ph": {"Hasil": "6.5", "Satuan": "pH"},
                "glucose": {"Hasil": "Negative"}
            }
        }
        base = _default_payload()
        
        _process_measurement_sections(norm, base)
        
        self.assertEqual(base["URINALYSIS"]["ph"]["Hasil"], "6.5")
        self.assertEqual(base["URINALYSIS"]["glucose"]["Hasil"], "Negative")
    
    def test_collect_extra_sections_with_multiple_extras(self):
        from ocr.utils.normalization import _collect_extra_sections
        
        norm = {
            "DEMOGRAPHY": {},
            "CUSTOM_1": {"data": "value1"},
            "CUSTOM_2": {"data": "value2"},
            "VITAL_SIGNS": {},
            "CUSTOM_3": {"data": "value3"}
        }
        
        extras = _collect_extra_sections(norm)
        
        self.assertEqual(len(extras), 3)
        self.assertIn("CUSTOM_1", extras)
        self.assertIn("CUSTOM_2", extras)
        self.assertIn("CUSTOM_3", extras)
        self.assertNotIn("DEMOGRAPHY", extras)
        self.assertNotIn("VITAL_SIGNS", extras)
