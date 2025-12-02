from django.test import TestCase
from unittest.mock import patch, Mock
from django.core.files.uploadedfile import SimpleUploadedFile


class ViewsEdgeCasesTests(TestCase):
    
    @patch('ocr.views.os.getenv')
    def test_create_supabase_client_returns_none_without_env(self, mock_getenv):
        mock_getenv.return_value = None
        
        from ocr.views import _create_supabase_client
        result = _create_supabase_client()
        
        self.assertIsNone(result)
    
    @patch('ocr.views.create_client')
    @patch('ocr.views.os.getenv')
    def test_create_supabase_client_with_credentials(self, mock_getenv, mock_create_client):

        mock_getenv.side_effect = lambda key: {
            "SUPABASE_URL": "http://test.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "test-key"
        }.get(key)
        
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        from ocr.views import _create_supabase_client
        result = _create_supabase_client()
        
        self.assertEqual(result, mock_client)
    
    @patch('ocr.views.GeminiService')
    @patch('ocr.views.os.getenv')
    def test_handle_upload_exception_handling(self, mock_getenv, mock_gemini):

        mock_getenv.return_value = "test-key"
        mock_gemini.side_effect = Exception("Test error")
        
        fake_pdf = SimpleUploadedFile("test.pdf", b"%PDF-1.4\n%EOF\n", content_type="application/pdf")
        response = self.client.post("/ocr/", {"pdf": fake_pdf})
        
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("error", data)

class OCRViewsIntegrationTests(TestCase):
    
    def test_get_request_renders_template(self):

        response = self.client.get("/ocr/")
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "ocr.html")
    
    @patch('ocr.views.DocumentService')
    @patch('ocr.views.StorageService')
    @patch('ocr.views.GeminiService')
    @patch('ocr.views.os.getenv')
    def test_successful_upload_full_flow(self, mock_getenv, mock_gemini_cls, mock_storage_cls, mock_doc_cls):

        # Setup env
        mock_getenv.side_effect = lambda key: {
            "GEMINI_API_KEY": "test-key",
            "SUPABASE_URL": "http://test.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "test-key"
        }.get(key)
        
        # Mock GeminiService
        mock_gemini = Mock()
        mock_gemini.extract_medical_data.return_value = {
            "parsed": {"DEMOGRAPHY": {"age": "25"}},
            "raw_text": "raw text",
            "processing_time": 1.5
        }
        mock_gemini_cls.return_value = mock_gemini
        
        # Mock StorageService
        mock_storage = Mock()
        mock_storage.save_pdf_locally.return_value = "/media/test.pdf"
        mock_storage.upload_to_supabase.return_value = {
            "pdf_url": "http://supabase.co/test.pdf",
            "json_url": "http://supabase.co/test.json"
        }
        mock_storage_cls.return_value = mock_storage
        
        # Mock DocumentService
        from annotation.models import Document
        mock_doc = Mock(spec=Document)
        mock_doc.id = 1
        mock_doc.content_url = "http://supabase.co/test.pdf"
        mock_pat = Mock()
        mock_pat.id = 1
        
        mock_doc_service = Mock()
        mock_doc_service.create_document_and_patient.return_value = (mock_doc, mock_pat)
        mock_doc_cls.return_value = mock_doc_service
        
        # Make request
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake_pdf = SimpleUploadedFile("test.pdf", b"%PDF-1.4\n%EOF\n", content_type="application/pdf")
        
        response = self.client.post("/ocr/", {"pdf": fake_pdf})
        
        # Verify success
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["document_id"], 1)
        self.assertEqual(data["patient_id"], 1)
        self.assertEqual(data["processing_time"], 1.5)
        
        # Verify all services were called
        mock_gemini.extract_medical_data.assert_called_once()
        mock_storage.save_pdf_locally.assert_called_once()
        mock_storage.upload_to_supabase.assert_called_once()
        mock_doc_service.create_document_and_patient.assert_called_once()
    
    @patch('ocr.views.GeminiService')
    @patch('ocr.views.os.getenv')
    def test_upload_with_supabase_url_preference(self, mock_getenv, mock_gemini_cls):

        mock_getenv.side_effect = lambda key: {
            "GEMINI_API_KEY": "test-key",
            "SUPABASE_URL": "http://test.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "test-key"
        }.get(key)
        
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake_pdf = SimpleUploadedFile("test.pdf", b"%PDF-1.4\n%EOF\n", content_type="application/pdf")
        
        with patch('ocr.views.StorageService') as mock_storage_cls:
            with patch('ocr.views.DocumentService') as mock_doc_cls:
                mock_storage = Mock()
                mock_storage.save_pdf_locally.return_value = "/media/local.pdf"
                mock_storage.upload_to_supabase.return_value = {
                    "pdf_url": "http://supabase.co/test.pdf",
                    "json_url": "http://supabase.co/test.json"
                }
                mock_storage_cls.return_value = mock_storage
                
                mock_gemini = Mock()
                mock_gemini.extract_medical_data.return_value = {
                    "parsed": {},
                    "raw_text": "",
                    "processing_time": 1.0
                }
                mock_gemini_cls.return_value = mock_gemini
                
                from annotation.models import Document
                mock_doc = Mock(spec=Document)
                mock_doc.id = 1
                mock_doc.content_url = "http://supabase.co/test.pdf"
                mock_pat = Mock()
                mock_pat.id = 1
                
                mock_doc_service = Mock()
                mock_doc_service.create_document_and_patient.return_value = (mock_doc, mock_pat)
                mock_doc_cls.return_value = mock_doc_service
                
                response = self.client.post("/ocr/", {"pdf": fake_pdf})
                
                # Verify Supabase URL was used
                call_args = mock_doc_service.create_document_and_patient.call_args
                pdf_url_arg = call_args[0][1]
                self.assertEqual(pdf_url_arg, "http://supabase.co/test.pdf")
    
    @patch("ocr.views.notify_ocr_completed")
    @patch("ocr.views.DocumentService")
    @patch("ocr.views.StorageService")
    @patch("ocr.views.GeminiService")
    @patch("ocr.views.os.getenv")
    def test_notify_completed_called_when_session_present(
        self,
        mock_getenv,
        mock_gemini_cls,
        mock_storage_cls,
        mock_doc_cls,
        mock_notify_completed,
    ):
        # Only GEMINI_API_KEY is needed; Supabase can be None
        mock_getenv.side_effect = lambda key: {
            "GEMINI_API_KEY": "test-key",
        }.get(key)

        # Make the request carry a session cookie
        self.client.cookies["sessionid"] = "sess-123"

        # Fake PDF upload
        fake_pdf = SimpleUploadedFile(
            "test.pdf", b"%PDF-1.4\n%EOF\n", content_type="application/pdf"
        )

        # Mock GeminiService
        mock_gemini = Mock()
        mock_gemini.extract_medical_data.return_value = {
            "parsed": {},
            "raw_text": "",
            "processing_time": 1.0,
        }
        mock_gemini_cls.return_value = mock_gemini

        # Mock StorageService
        mock_storage = Mock()
        mock_storage.save_pdf_locally.return_value = "/media/local.pdf"
        mock_storage.upload_to_supabase.return_value = {
            "pdf_url": None,
            "json_url": None,
        }
        mock_storage_cls.return_value = mock_storage

        # Mock DocumentService
        mock_doc_service = Mock()
        mock_doc = Mock()
        mock_pat = Mock()
        mock_doc_service.create_document_and_patient.return_value = (mock_doc, mock_pat)
        mock_doc_cls.return_value = mock_doc_service

        # Do the POST
        response = self.client.post("/ocr/", {"pdf": fake_pdf})
        self.assertEqual(response.status_code, 200)

        # notify_ocr_completed should have been called once
        mock_notify_completed.assert_called_once()
        args, kwargs = mock_notify_completed.call_args
        self.assertEqual(args[0], "sess-123")          # session_id
        self.assertEqual(kwargs["path"], "/media/local.pdf")
    
    @patch("ocr.views.notify_ocr_failed")
    @patch("ocr.views.GeminiService")
    @patch("ocr.views.os.getenv")
    def test_notify_failed_called_on_exception(
        self,
        mock_getenv,
        mock_gemini_cls,
        mock_notify_failed,
    ):
        mock_getenv.side_effect = lambda key: {
            "GEMINI_API_KEY": "test-key",
        }.get(key)

        # Request carries session cookie so failure path will notify
        self.client.cookies["sessionid"] = "sess-err"

        # Make constructing GeminiService raise inside the try-block
        mock_gemini_cls.side_effect = Exception("boom")

        fake_pdf = SimpleUploadedFile(
            "test.pdf", b"%PDF-1.4\n%EOF\n", content_type="application/pdf"
        )

        response = self.client.post("/ocr/", {"pdf": fake_pdf})
        self.assertEqual(response.status_code, 200)

        mock_notify_failed.assert_called_once()
        args, kwargs = mock_notify_failed.call_args
        self.assertEqual(args[0], "sess-err")
        # When failing, view uses pdf_file.name
        self.assertEqual(kwargs["path"], "test.pdf")


    
class OCRViewsFallbackTests(TestCase):
    @patch('ocr.views.os.getenv')
    def test_upload_falls_back_to_local_url(self, mock_getenv):
        mock_getenv.side_effect = lambda key: {
            "GEMINI_API_KEY": "test-key",
        }.get(key)

        from django.core.files.uploadedfile import SimpleUploadedFile
        fake_pdf = SimpleUploadedFile(
            "test.pdf",
            b"%PDF-1.4\n%EOF\n",
            content_type="application/pdf",
        )

        with patch('ocr.views.GeminiService') as mock_gemini_cls:
            with patch('ocr.views.StorageService') as mock_storage_cls:
                with patch('ocr.views.DocumentService') as mock_doc_cls:
                    mock_gemini = Mock()
                    mock_gemini.extract_medical_data.return_value = {
                        "parsed": {},
                        "raw_text": "",
                        "processing_time": 1.0,
                    }
                    mock_gemini_cls.return_value = mock_gemini

                    mock_storage = Mock()
                    mock_storage.save_pdf_locally.return_value = "/media/local.pdf"
                    mock_storage.upload_to_supabase.return_value = {
                        "pdf_url": None,
                        "json_url": None,
                    }
                    mock_storage_cls.return_value = mock_storage

                    # Mock DocumentService
                    from annotation.models import Document
                    mock_doc = Mock(spec=Document)
                    mock_doc.id = 1
                    mock_doc.content_url = "/media/local.pdf"

                    mock_pat = Mock()
                    mock_pat.id = 1

                    mock_doc_service = Mock()
                    mock_doc_service.create_document_and_patient.return_value = (
                        mock_doc,
                        mock_pat,
                    )
                    mock_doc_cls.return_value = mock_doc_service

                    # Make request
                    response = self.client.post("/ocr/", {"pdf": fake_pdf})

                    call_args = mock_doc_service.create_document_and_patient.call_args
                    pdf_url_arg = call_args[0][1]
                    self.assertEqual(pdf_url_arg, "/media/local.pdf")

                    # Verify
                    self.assertEqual(response.status_code, 200)
                    data = response.json()
                    self.assertTrue(data["success"])
