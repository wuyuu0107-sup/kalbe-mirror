from django.test import TestCase
from unittest.mock import Mock, patch
from ocr.services.document import DocumentService
from ocr.services.gemini import GeminiService
from ocr.services.storage import StorageService
from annotation.models import Document, Patient
from unittest import TestCase
from unittest.mock import patch



class DocumentServiceTests(TestCase):
    
    def setUp(self):
        self.service = DocumentService()
    
    def test_creates_document_and_patient(self):
        ordered_data = {"DEMOGRAPHY": {"age": 25}}
        pdf_url = "https://example.com/test.pdf"
        supabase_urls = {"pdf_url": pdf_url, "json_url": "https://example.com/test.json"}
        local_url = "/media/test.pdf"
        
        doc, pat = self.service.create_document_and_patient(
            ordered_data, pdf_url, supabase_urls, local_url
        )
        
        self.assertIsInstance(doc, Document)
        self.assertIsInstance(pat, Patient)
        self.assertEqual(doc.source, "pdf")
        self.assertEqual(doc.content_url, pdf_url)
        self.assertEqual(doc.payload_json, ordered_data)
    
    def test_document_has_correct_meta(self):
        ordered_data = {"DEMOGRAPHY": {"age": 25}}
        pdf_url = "https://example.com/test.pdf"
        supabase_urls = {"pdf_url": pdf_url, "json_url": "https://example.com/test.json"}
        local_url = "/media/test.pdf"
        
        doc, _ = self.service.create_document_and_patient(
            ordered_data, pdf_url, supabase_urls, local_url
        )
        
        self.assertIn("from", doc.meta)
        self.assertIn("section_order", doc.meta)
        self.assertEqual(doc.meta["from"], "gemini_2_5")
        self.assertEqual(doc.meta["local_fallback_url"], local_url)
        self.assertEqual(doc.meta["storage_pdf_url"], pdf_url)
        self.assertEqual(doc.meta["storage_json_url"], "https://example.com/test.json")
    
    def test_patient_created_with_default_values(self):
        ordered_data = {"DEMOGRAPHY": {"age": 25}}
        pdf_url = "https://example.com/test.pdf"
        supabase_urls = {"pdf_url": pdf_url, "json_url": "https://example.com/test.json"}
        local_url = "/media/test.pdf"
        
        _, pat = self.service.create_document_and_patient(
            ordered_data, pdf_url, supabase_urls, local_url
        )
        
        self.assertEqual(pat.name, "OCR Patient")
        self.assertEqual(pat.external_id, "OCR-ADHOC")




class GeminiServiceTests(TestCase):
    def setUp(self):
        self.api_key = "fake-key"

    @patch("ocr.services.gemini.genai") 
    def test_service_initialization(self, mock_genai):
        GeminiService(api_key=self.api_key)
        mock_genai.configure.assert_called_once_with(api_key=self.api_key)
        mock_genai.GenerativeModel.assert_called_once_with("gemini-2.5-flash")

    @patch('ocr.services.gemini.genai')
    def test_extract_returns_parsed_data(self, mock_genai):
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = '{"DEMOGRAPHY": {"age": 25}}'
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        service = GeminiService(self.api_key)
        result = service.extract_medical_data(b"fake_pdf")
        
        self.assertIn("parsed", result)
        self.assertIn("raw_text", result)
        self.assertIn("processing_time", result)
        self.assertEqual(result["parsed"]["DEMOGRAPHY"]["age"], 25)
    
    @patch('ocr.services.gemini.genai')
    def test_cleans_json_code_fences(self, mock_genai):
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = '```json\n{"data": "value"}\n```'
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        service = GeminiService(self.api_key)
        result = service.extract_medical_data(b"fake_pdf")
        
        self.assertNotIn("```", result["raw_text"])
        self.assertEqual(result["parsed"]["data"], "value")
    
    @patch('ocr.services.gemini.genai')
    def test_handles_invalid_json_with_regex_fallback(self, mock_genai):
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = 'Some text before {"valid": "json"}'
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        service = GeminiService(self.api_key)
        result = service.extract_medical_data(b"fake_pdf")
        
        self.assertEqual(result["parsed"]["valid"], "json")
    
    @patch('ocr.services.gemini.genai')
    def test_handles_completely_invalid_json(self, mock_genai):
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = 'completely invalid'
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        
        service = GeminiService(self.api_key)
        result = service.extract_medical_data(b"fake_pdf")
        
        self.assertEqual(result["parsed"], {})
    
    @patch('ocr.services.gemini.genai')
    def test_get_prompt_returns_string(self, mock_genai):
        service = GeminiService(self.api_key)
        prompt = service._get_prompt()
        
        self.assertIsInstance(prompt, str)
        self.assertIn("DEMOGRAPHY", prompt)
        self.assertIn("JSON", prompt)


class StorageServiceTests(TestCase):
    
    def setUp(self):
        self.service = StorageService()
    
    @patch('ocr.services.storage.default_storage')
    def test_save_pdf_locally_returns_url(self, mock_storage):
        mock_storage.save.return_value = "ocr/test.pdf"
        mock_storage.url.return_value = "/media/ocr/test.pdf"
        
        result = self.service.save_pdf_locally("test.pdf", b"fake_pdf")
        
        self.assertEqual(result, "/media/ocr/test.pdf")
        mock_storage.save.assert_called_once()
    
    @patch('ocr.services.storage.default_storage')
    @patch('ocr.services.storage.settings')
    def test_save_pdf_locally_handles_url_exception(self, mock_settings, mock_storage):
        mock_storage.save.return_value = "ocr/test.pdf"
        mock_storage.url.side_effect = Exception("URL error")
        mock_settings.MEDIA_URL = "/media/"
        
        result = self.service.save_pdf_locally("test.pdf", b"fake_pdf")
        
        self.assertEqual(result, "/media/ocr/test.pdf")
    
    def test_upload_without_supabase_returns_none_urls(self):
        service = StorageService(supabase_client=None)
        
        result = service.upload_to_supabase("test.pdf", b"fake", {})
        
        self.assertIsNone(result["pdf_url"])
        self.assertIsNone(result["json_url"])
    
    def test_generate_storage_path_sanitizes_filename(self):
        result = self.service._generate_storage_path("test file!@#.pdf")
        
        self.assertNotIn(" ", result)
        self.assertNotIn("!", result)
        self.assertIn(".pdf", result)

    def test_extract_url_from_string(self):
        result = self.service._extract_url_from_response("https://example.com/file.pdf?")
        self.assertEqual(result, "https://example.com/file.pdf")
    
    def test_extract_url_preserves_query_params(self):
        result = self.service._extract_url_from_response("https://example.com/file.pdf?token=123")
        self.assertEqual(result, "https://example.com/file.pdf?token=123")

    def test_extract_url_from_dict_with_signed_url(self):
        response = {"signedURL": "https://example.com/file.pdf?"}
        
        result = self.service._extract_url_from_response(response)
        
        self.assertEqual(result, "https://example.com/file.pdf")
    
    def test_extract_url_from_dict_with_public_url(self):
        response = {"publicURL": "https://example.com/file.pdf?"}
        
        result = self.service._extract_url_from_response(response)
        
        self.assertEqual(result, "https://example.com/file.pdf")
    
    def test_extract_url_returns_none_for_invalid_input(self):
        result = self.service._extract_url_from_response(None)
        
        self.assertIsNone(result)
    
    def test_extract_url_from_dict_without_url_keys(self):
        response = {"other_key": "value"}
        
        result = self.service._extract_url_from_response(response)
        
        self.assertIsNone(result)
    
    @patch('ocr.services.storage.os.getenv')
    def test_upload_to_supabase_with_client(self, mock_getenv):
        mock_getenv.return_value = "test-bucket"
        
        mock_supabase = Mock()
        mock_storage = Mock()
        mock_supabase.storage.from_.return_value = mock_storage
        
        mock_storage.upload.return_value = None
        mock_storage.create_signed_url.return_value = "https://example.com/file.pdf"
        mock_storage.get_public_url.return_value = "https://example.com/file.json"
        
        service = StorageService(supabase_client=mock_supabase)
        result = service.upload_to_supabase("test.pdf", b"fake_pdf", {"data": "test"})
        
        self.assertIn("pdf_url", result)
        self.assertIn("json_url", result)
    
    def test_upload_pdf_to_storage_handles_signed_url_exception(self):
        mock_storage = Mock()
        mock_storage.upload.return_value = None
        mock_storage.create_signed_url.side_effect = Exception("Signed URL error")
        
        result = self.service._upload_pdf_to_storage(
            mock_storage, "test_path", b"fake_pdf", "test.pdf"
        )
        
        self.assertIsNone(result)
    
    def test_upload_json_to_storage_handles_all_exceptions(self):
        mock_storage = Mock()
        mock_storage.upload.return_value = None
        mock_storage.get_public_url.side_effect = Exception("Public URL error")
        mock_storage.create_signed_url.side_effect = Exception("Signed URL error")
        
        result = self.service._upload_json_to_storage(
            mock_storage, "test_path", {"data": "test"}
        )
        
        self.assertIsNone(result)

    @patch('ocr.services.storage.os.getenv')
    def test_upload_json_with_successful_public_url(self, mock_getenv):
        
        mock_getenv.return_value = "test-bucket"
        
        mock_supabase = Mock()
        mock_storage = Mock()
        mock_supabase.storage.from_.return_value = mock_storage
        
        mock_storage.upload.return_value = None
        
        # Simulate successful public URL retrieval
        mock_storage.get_public_url.return_value = {"publicURL": "https://example.com/file.json"}
        mock_storage.create_signed_url.return_value = "https://example.com/file.pdf"
        
        service = StorageService(supabase_client=mock_supabase)
        result = service.upload_to_supabase("test.pdf", b"fake_pdf", {"data": "test"})
        
        self.assertEqual(result["json_url"], "https://example.com/file.json")
        mock_storage.get_public_url.assert_called_once()

    def test_upload_json_successful_public_url_first_try(self):
        """Cover line 85 - get_public_url succeeds on first try"""
        mock_storage = Mock()
        mock_storage.upload.return_value = None

        # First try with get_public_url succeeds
        mock_storage.get_public_url.return_value = "https://example.com/file.json"
        
        result = self.service._upload_json_to_storage(
            mock_storage, "test_path", {"data": "test"}
        )
        
        self.assertEqual(result, "https://example.com/file.json")
        mock_storage.get_public_url.assert_called_once()
        mock_storage.create_signed_url.assert_not_called()

def test_upload_json_with_successful_get_public_url(self):
    
    mock_storage = Mock()
    mock_storage.upload.return_value = None
    
    mock_storage.get_public_url.return_value = "https://example.com/test.json"
    
    result = self.service._upload_json_to_storage(
        mock_storage, 
        "test_path.pdf",
        {"data": "test"}
    )
    
    self.assertEqual(result, "https://example.com/test.json")
    
    mock_storage.get_public_url.assert_called_once_with("test_path.json")
    mock_storage.create_signed_url.assert_not_called()