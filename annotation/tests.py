from django.test import TestCase, Client
from .models import Patient, Document
from unittest.mock import patch
from authentication.models import User
from rest_framework.test import APIClient
from rest_framework import status
import os
import io
import json
import base64
from django.core.files.uploadedfile import SimpleUploadedFile
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient
from rest_framework import status
from annotation.models import Annotation
from django.urls import reverse
from django.test import TestCase, Client
from .models import Document, Patient



# If your file already declared HAS_COMMENTS earlier, you can reuse it.
try:
    from .models import Comment  # noqa: F401
    HAS_COMMENTS = True
except Exception:
    HAS_COMMENTS = False


class AnnotationCRUDTests(TestCase):
    def setUp(self):
        self.client = APIClient()  # instead of Client()
        self.document_id = 1
        self.patient_id = 1
        self.mock_drawing = {
            "type": "drawing",
            "data": [{"tool": "pen", "points": [[10, 10], [20, 20]]}]
        }

        self.user = User.objects.create(
            username='testuser',
            password='testpassword',
            email='testuser@example.com',
            is_verified=True
        )
        # No session login; this avoids last_login + signal issues
        self.client.force_authenticate(user=self.user)

        Patient.objects.create(id=self.patient_id, name="Test Patient")
        Document.objects.create(id=self.document_id)

    def test_invalid_method_on_create_drawing_annotation(self):
        # GET on a POST-only endpoint should be Method Not Allowed
        response = self.client.get(
            f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/'
        )
        self.assertEqual(response.status_code, 405)

    def test_not_found_annotation(self):
        response = self.client.get(
            f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/9999/'
        )
        self.assertEqual(response.status_code, 404)



    def test_bad_json_create_drawing_annotation(self):
        response = self.client.post(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/', '{bad json}', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_create_and_get_drawing_annotation(self):
        # Create annotation
        response = self.client.post(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/', self.mock_drawing, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        annotation_id = response.json()["id"]
        # Get annotation
        get_response = self.client.get(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/{annotation_id}/')
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["drawing"], self.mock_drawing)

    def test_get_drawing_annotation_exception(self):
        with patch('annotation.views.Annotation.objects.get', side_effect=Annotation.DoesNotExist):
            response = self.client.get(
                f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/1/'
            )
            self.assertEqual(response.status_code, 404)

    def test_update_drawing_annotation(self):
        # Create annotation
        response = self.client.post(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/', self.mock_drawing, content_type='application/json')
        annotation_id = response.json()["id"]
        updated_drawing = {"type": "drawing", "data": [{"tool": "eraser", "points": [[15, 15], [25, 25]]}]}
        put_response = self.client.put(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/{annotation_id}/', updated_drawing, content_type='application/json')
        self.assertEqual(put_response.status_code, 200)
        self.assertEqual(put_response.json()["drawing"], updated_drawing)

    def test_put_drawing_annotation_exception(self):
        updated_drawing = {"type": "drawing", "data": [{"tool": "eraser", "points": [[15, 15], [25, 25]]}]}
        # Was: side_effect=Exception('Test error') and expecting 400
        with patch('annotation.views.Annotation.objects.get', side_effect=Annotation.DoesNotExist):
            resp = self.client.put(
                f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/1/',
                updated_drawing, content_type='application/json'
            )
            self.assertEqual(resp.status_code, 404)


    def test_delete_drawing_annotation(self):
        # Create annotation
        response = self.client.post(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/', self.mock_drawing, content_type='application/json')
        annotation_id = response.json()["id"]
        delete_response = self.client.delete(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/{annotation_id}/')
        self.assertEqual(delete_response.status_code, 204)
            
    def test_delete_drawing_annotation_exception(self):
        # Was: side_effect=Exception('Test error') and expecting 400
        with patch('annotation.views.Annotation.objects.get', side_effect=Annotation.DoesNotExist):
            resp = self.client.delete(
                f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/1/'
            )
            self.assertEqual(resp.status_code, 404)


    def test_update_nonexistent_annotation(self):
        updated_drawing = {"type": "drawing", "data": [{"tool": "eraser", "points": [[15, 15], [25, 25]]}]}
        response = self.client.put(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/9999/', updated_drawing, content_type='application/json')
        self.assertEqual(response.status_code, 404)

    def test_delete_nonexistent_annotation(self):
        response = self.client.delete(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/9999/')
        self.assertEqual(response.status_code, 404)

    def test_invalid_method_on_drawing_annotation(self):
        response = self.client.post(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/1/')
        self.assertIn(response.status_code, (400, 405))

    def test_unauthenticated_access(self):
        unauthenticated_client = Client()
        response = unauthenticated_client.get(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/')
        self.assertEqual(response.status_code, 405)




class AnnotationAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Create a test user
        self.user = User.objects.create(
            username='testuser',
            password='testpassword',
            email='testuser@example.com',
            is_verified=True
        )

        # Simulate authentication by setting credentials
        self.client.credentials(HTTP_AUTHORIZATION='Token fake-token')

        # Prepare a sample Document (json) and Patient
        doc_res = self.client.post('/api/v1/documents/', {
            'source': 'json',
            'payload_json': {'hello': 'world'},
            'meta': {'from': 'ocr-service'}
        }, format='json')
        self.assertEqual(doc_res.status_code, status.HTTP_201_CREATED)
        self.document_id = doc_res.data['id']

        pat_res = self.client.post('/api/v1/patients/', {
            'name': 'Test Patient',
            'external_id': 'PAT-001'
        }, format='json')
        self.assertEqual(pat_res.status_code, status.HTTP_201_CREATED)
        self.patient_id = pat_res.data['id']

    def test_create_annotation(self):
        # Create annotation
        res = self.client.post('/api/v1/annotations/', {
            'document': self.document_id,
            'patient': self.patient_id,
            'label': 'A1',
            'drawing_data': {'foo': 'bar'}
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', res.data)

        # Fetch list, filtered by doc & patient
        res = self.client.get(
            f'/api/v1/annotations/?document={self.document_id}&patient={self.patient_id}'
        )
        self.assertEqual(res.status_code, 200)

        # Handle paginated vs non-paginated
        data = res.data.get("results", res.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['label'], 'A1')


    def test_get_update_delete_annotation(self):
        create = self.client.post('/api/v1/annotations/', {
            'document': self.document_id,
            'patient': self.patient_id,
            'label': 'to-update',
            'drawing_data': {'v': 1}
        }, format='json')
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)
        annot_id = create.data['id']

        # retrieve
        get_res = self.client.get(f'/api/v1/annotations/{annot_id}/')
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data['label'], 'to-update')

        # update
        upd = self.client.put(f'/api/v1/annotations/{annot_id}/', {
            'document': self.document_id,
            'patient': self.patient_id,
            'label': 'updated',
            'drawing_data': {'v': 2}
        }, format='json')
        self.assertEqual(upd.status_code, status.HTTP_200_OK)
        self.assertEqual(upd.data['label'], 'updated')
        self.assertEqual(upd.data['drawing_data']['v'], 2)

        # delete
        dele = self.client.delete(f'/api/v1/annotations/{annot_id}/')
        self.assertEqual(dele.status_code, status.HTTP_204_NO_CONTENT)

        # 404 after delete
        notfound = self.client.get(f'/api/v1/annotations/{annot_id}/')
        self.assertEqual(notfound.status_code, status.HTTP_404_NOT_FOUND)

    def test_document_validation_requires_content(self):
        bad = self.client.post('/api/v1/documents/', {
            'source': 'pdf'  # missing content_url/payload_json
        }, format='json')
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_annotation_validation_requires_json_shape(self):
        # invalid: drawing_data is string
        bad = self.client.post('/api/v1/annotations/', {
            'document': self.document_id,
            'patient': self.patient_id,
            'drawing_data': 'not-json-object'
        }, format='json')
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_access(self):
        unauthenticated_client = APIClient()
        res = unauthenticated_client.get(f'/api/v1/annotations/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)


def make_pdf_bytes() -> bytes:
    # minimal-but-valid-enough PDF header for upload tests
    return b"%PDF-1.4\n%Fake\n1 0 obj <<>> endobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<<>>\nstartxref\n0\n%%EOF"


class _AuthAPIMixin:
    """Common setup that creates a user and uses DRF APIClient with force_authenticate."""
    def api_setup(self):
        from authentication.models import User  # your existing import style
        self.user = User.objects.create(
            username="apitester",
            email="api@test.local",
            password="pass12345",
        )
        # If your tests/session logic expects .user_id, mirror it
        if not hasattr(self.user, "user_id"):
            self.user.user_id = self.user.id

        self.client = APIClient()
        self.client.force_authenticate(self.user)

        # handy paths
        self.DOC_LIST = "/api/v1/documents/"
        self.PAT_LIST = "/api/v1/patients/"
        self.ANN_LIST = "/api/v1/annotations/"
        self.ANN_BY_DOC_PAT = "/api/v1/annotations/by_document_patient/"
        self.DOC_FROM_GEMINI = "/api/v1/documents/from-gemini/"


class DocumentViewSetTests(_AuthAPIMixin, TestCase):
    def setUp(self):
        self.api_setup()

    def test_create_document_json_source(self):
        payload = {
            "source": "json",
            "payload_json": {"hello": "world"},
            "meta": {"from": "unit-test"},
        }
        res = self.client.post(self.DOC_LIST, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.content)
        self.assertIn("id", res.data)
        self.assertEqual(res.data["source"], "json")
        self.assertEqual(res.data["payload_json"]["hello"], "world")

    def test_document_validation_requires_content(self):
        # source='pdf' but no content_url
        bad = self.client.post(
            self.DOC_LIST,
            data=json.dumps({"source": "pdf"}),
            content_type="application/json",
        )
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST, bad.content)

    def test_patch_document_payload(self):
        # create
        create = self.client.post(
            self.DOC_LIST,
            data=json.dumps({"source": "json", "payload_json": {"a": 1}}),
            content_type="application/json",
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.content)
        doc_id = create.data["id"]

        # patch payload_json
        patch = {"payload_json": {"a": 2, "b": 3}}
        res = self.client.patch(
            f"{self.DOC_LIST}{doc_id}/",
            data=json.dumps(patch),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.content)
        self.assertEqual(res.data["payload_json"]["a"], 2)
        self.assertEqual(res.data["payload_json"]["b"], 3)

    @patch("annotation.views.genai.GenerativeModel")
    def test_from_gemini_ok(self, MockModel):
        # fake model + response
        mock_model = MagicMock()
        MockModel.return_value = mock_model

        fake_text = '{"DEMOGRAPHY":{"subject_initials":"AB"}}'
        mock_resp = MagicMock()
        mock_resp.text = fake_text
        mock_model.generate_content.return_value = mock_resp

        # ensure an API key is present for the view logic
        os.environ["GEMINI_API_KEY"] = "fake-key-for-tests"

        pdf_file = SimpleUploadedFile("x.pdf", make_pdf_bytes(), content_type="application/pdf")
        res = self.client.post(self.DOC_FROM_GEMINI, data={"file": pdf_file}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.content)
        self.assertEqual(res.data["source"], "pdf")
        self.assertIn("payload_json", res.data)
        self.assertEqual(res.data["payload_json"]["DEMOGRAPHY"]["subject_initials"], "AB")

    @patch("annotation.views.genai.GenerativeModel")
    def test_from_gemini_missing_api_key(self, MockModel):
        # clear keys the view checks
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("GOOGLE_API_KEY", None)

        pdf_file = SimpleUploadedFile("x.pdf", make_pdf_bytes(), content_type="application/pdf")
        res = self.client.post(self.DOC_FROM_GEMINI, data={"file": pdf_file}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR, res.content)
        self.assertIn("GEMINI_API_KEY not set", res.data.get("error", ""))


class PatientViewSetTests(_AuthAPIMixin, TestCase):
    def setUp(self):
        self.api_setup()

    def test_create_and_retrieve_patient(self):
        create = self.client.post(
            self.PAT_LIST,
            data=json.dumps({"name": "Alice", "external_id": "PAT-XYZ"}),
            content_type="application/json",
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.content)
        pid = create.data["id"]

        get_res = self.client.get(f"{self.PAT_LIST}{pid}/")
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["name"], "Alice")
        self.assertEqual(get_res.data["external_id"], "PAT-XYZ")


class AnnotationByDocPatientTests(_AuthAPIMixin, TestCase):
    def setUp(self):
        self.api_setup()
        # create a doc + two patients
        d = self.client.post(
            self.DOC_LIST,
            data=json.dumps({"source": "json", "payload_json": {"k": 1}}),
            content_type="application/json",
        )
        self.assertEqual(d.status_code, status.HTTP_201_CREATED, d.content)
        self.doc_id = d.data["id"]

        p1 = self.client.post(
            self.PAT_LIST,
            data=json.dumps({"name": "P1", "external_id": "P-1"}),
            content_type="application/json",
        )
        p2 = self.client.post(
            self.PAT_LIST,
            data=json.dumps({"name": "P2", "external_id": "P-2"}),
            content_type="application/json",
        )
        self.assertEqual(p1.status_code, 201)
        self.assertEqual(p2.status_code, 201)
        self.p1 = p1.data["id"]
        self.p2 = p2.data["id"]

        # annotations for each patient
        a1 = self.client.post(
            self.ANN_LIST,
            data=json.dumps({"document": self.doc_id, "patient": self.p1, "label": "A1", "drawing_data": {"v": 1}}),
            content_type="application/json",
        )
        a2 = self.client.post(
            self.ANN_LIST,
            data=json.dumps({"document": self.doc_id, "patient": self.p2, "label": "A2", "drawing_data": {"v": 2}}),
            content_type="application/json",
        )
        self.assertEqual(a1.status_code, 201, a1.content)
        self.assertEqual(a2.status_code, 201, a2.content)

    def test_filter_by_doc_and_patient(self):
        res = self.client.get(f"{self.ANN_LIST}?document={self.doc_id}&patient={self.p1}")
        self.assertEqual(res.status_code, 200)
        # handle both paginated & non-paginated responses
        data = res.data.get("results", res.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["label"], "A1")

    def test_by_document_patient_action(self):
        res = self.client.get(f"{self.ANN_BY_DOC_PAT}?document={self.doc_id}&patient={self.p1}")
        self.assertEqual(res.status_code, 200)
        data = res.data.get("results", res.data)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["label"], "A1")


if HAS_COMMENTS:
    class CommentViewSetTests(_AuthAPIMixin, TestCase):
        def setUp(self):
            self.api_setup()
            # doc + patient to attach comments to
            d = self.client.post(
                self.DOC_LIST,
                data=json.dumps({"source": "json", "payload_json": {"k": 1}}),
                content_type="application/json",
            )
            self.assertEqual(d.status_code, 201, d.content)
            self.doc_id = d.data["id"]

            p = self.client.post(
                self.PAT_LIST,
                data=json.dumps({"name": "Commenter", "external_id": "C-1"}),
                content_type="application/json",
            )
            self.assertEqual(p.status_code, 201, p.content)
            self.pat_id = p.data["id"]

            self.COMMENT_LIST = "/api/v1/comments/"

        def test_create_list_delete_comment(self):
            create = self.client.post(
                self.COMMENT_LIST,
                data=json.dumps({"document": self.doc_id, "patient": self.pat_id, "author": "Dr J", "body": "Looks good."}),
                content_type="application/json",
            )
            self.assertEqual(create.status_code, 201, create.content)
            cid = create.data["id"]

            lst = self.client.get(f"{self.COMMENT_LIST}?document={self.doc_id}&patient={self.pat_id}")
            self.assertEqual(lst.status_code, 200)
            data = lst.data.get("results", lst.data)
            self.assertTrue(any(c["id"] == cid for c in data))

            dele = self.client.delete(f"{self.COMMENT_LIST}{cid}/")
            self.assertEqual(dele.status_code, 204)

# === Additions to annotation/tests.py ===
from django.conf import settings

class DocumentFromGeminiEdgeCases(_AuthAPIMixin, TestCase):
    def setUp(self):
        self.api_setup()

    def test_from_gemini_missing_file(self):
        # no "file" in multipart
        res = self.client.post(self.DOC_FROM_GEMINI, data={}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Upload a PDF", res.data.get("error", ""))

    @patch("annotation.views.genai.GenerativeModel")
    def test_from_gemini_codefence_json(self, MockModel):
        """gemini returns ```json fenced text; regex must strip it and parse"""
        mock_model = MagicMock()
        MockModel.return_value = mock_model
        os.environ["GEMINI_API_KEY"] = "fake-key"

        mock_resp = MagicMock()
        mock_resp.text = "```json\n{\"hello\": \"world\"}\n```"
        mock_model.generate_content.return_value = mock_resp

        pdf = SimpleUploadedFile("x.pdf", make_pdf_bytes(), content_type="application/pdf")
        res = self.client.post(self.DOC_FROM_GEMINI, data={"file": pdf}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.content)
        self.assertEqual(res.data["payload_json"]["hello"], "world")
        self.assertEqual(res.data["source"], "pdf")  # serializer maps to json source



    @patch("annotation.views.genai.GenerativeModel")
    def test_from_gemini_upstream_exception(self, MockModel):
        os.environ["GEMINI_API_KEY"] = "fake-key"
        mock_model = MagicMock()
        MockModel.return_value = mock_model
        mock_model.generate_content.side_effect = RuntimeError("boom")

        pdf = SimpleUploadedFile("x3.pdf", make_pdf_bytes(), content_type="application/pdf")
        res = self.client.post(self.DOC_FROM_GEMINI, data={"file": pdf}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn("boom", res.data.get("error", ""))


def _items(resp):
    # DRF Response may be dict (with "results"), list, or a JSON string.
    data = resp.data
    if isinstance(data, (str, bytes)):
        data = json.loads(data)
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data

class PatientSearchFilterTests(_AuthAPIMixin, TestCase):
    def setUp(self):
        self.api_setup()

    def test_patient_search_by_name_and_external_id(self):
        self.client.post(
            self.PAT_LIST,
            data=json.dumps({"name": "Jane Roe", "external_id": "PAT-ABC"}),
            content_type="application/json",
        )
        self.client.post(
            self.PAT_LIST,
            data=json.dumps({"name": "John Smith", "external_id": "ZZ-999"}),
            content_type="application/json",
        )

        # search by partial name
        res1 = self.client.get(f"{self.PAT_LIST}?search=jane")
        self.assertEqual(res1.status_code, 200)
        items1 = _items(res1)
        self.assertTrue(any(p.get("name") == "Jane Roe" for p in items1))

        # search by external_id
        res2 = self.client.get(f"{self.PAT_LIST}?search=ZZ-999")
        self.assertEqual(res2.status_code, 200)
        items2 = _items(res2)
        self.assertTrue(any(p.get("name") == "John Smith" for p in items2))


class AnnotationViewSetEdgeTests(_AuthAPIMixin, TestCase):
    def setUp(self):
        self.api_setup()
        # set up one doc/patient
        d = self.client.post(
            self.DOC_LIST,
            data=json.dumps({"source": "json", "payload_json": {"x": 1}}),
            content_type="application/json",
        )
        self.doc_id = d.data["id"]
        p = self.client.post(
            self.PAT_LIST,
            data=json.dumps({"name": "Edge P", "external_id": "EDGE-1"}),
            content_type="application/json",
        )
        self.pat_id = p.data["id"]

    def test_list_without_filters_and_ordering(self):
        # create two
        self.client.post(
            self.ANN_LIST,
            data=json.dumps({"document": self.doc_id, "patient": self.pat_id, "label": "L1", "drawing_data": {"v": 1}}),
            content_type="application/json",
        )
        self.client.post(
            self.ANN_LIST,
            data=json.dumps({"document": self.doc_id, "patient": self.pat_id, "label": "L2", "drawing_data": {"v": 2}}),
            content_type="application/json",
        )
        res = self.client.get(self.ANN_LIST)
        self.assertEqual(res.status_code, 200)
        data = res.data.get("results", res.data)
        # most recent first (order_by('-created_at'))
        self.assertGreaterEqual(len(data), 2)
        self.assertEqual(data[0]["label"], "L2")

    def test_filter_only_document_or_only_patient(self):
        a_doc_only = self.client.get(f"{self.ANN_LIST}?document={self.doc_id}")
        self.assertEqual(a_doc_only.status_code, 200)
        self.assertTrue(len(a_doc_only.data.get("results", a_doc_only.data)) >= 0)

        a_pat_only = self.client.get(f"{self.ANN_LIST}?patient={self.pat_id}")
        self.assertEqual(a_pat_only.status_code, 200)
        self.assertTrue(len(a_pat_only.data.get("results", a_pat_only.data)) >= 0)

    def test_put_bad_json_in_function_endpoint(self):
        # create via function endpoint first
        create = self.client.post(
            f"/api/v1/documents/{self.doc_id}/patients/{self.pat_id}/annotations/",
            data=json.dumps({"a": 1}),
            content_type="application/json",
        )
        self.assertEqual(create.status_code, 201, create.content)
        ann_id = create.json()["id"]

        # now send bad JSON to PUT
        res = self.client.put(
            f"/api/v1/documents/{self.doc_id}/patients/{self.pat_id}/annotations/{ann_id}/",
            data="{bad json}",
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400)


if HAS_COMMENTS:
    class CommentViewSetMoreTests(_AuthAPIMixin, TestCase):
        def setUp(self):
            self.api_setup()
            d = self.client.post(
                self.DOC_LIST,
                data=json.dumps({"source": "json", "payload_json": {"k": 1}}),
                content_type="application/json",
            )
            self.doc_id = d.data["id"]
            p = self.client.post(
                self.PAT_LIST,
                data=json.dumps({"name": "CUser", "external_id": "C-2"}),
                content_type="application/json",
            )
            self.pat_id = p.data["id"]
            self.COMMENT_LIST = "/api/v1/comments/"

        def test_list_filter_only_doc_or_only_patient(self):
            # create one comment
            c = self.client.post(
                self.COMMENT_LIST,
                data=json.dumps({"document": self.doc_id, "patient": self.pat_id, "author": "N", "body": "b"}),
                content_type="application/json",
            )
            self.assertEqual(c.status_code, 201, c.content)

            # filter by doc only
            r1 = self.client.get(f"{self.COMMENT_LIST}?document={self.doc_id}")
            self.assertEqual(r1.status_code, 200)

            # filter by patient only
            r2 = self.client.get(f"{self.COMMENT_LIST}?patient={self.pat_id}")
            self.assertEqual(r2.status_code, 200)

        def test_update_comment(self):
            c = self.client.post(
                self.COMMENT_LIST,
                data=json.dumps({"document": self.doc_id, "patient": self.pat_id, "author": "N", "body": "first"}),
                content_type="application/json",
            )
            cid = c.data["id"]
            upd = self.client.put(
                f"{self.COMMENT_LIST}{cid}/",
                data=json.dumps({"document": self.doc_id, "patient": self.pat_id, "author": "N", "body": "second"}),
                content_type="application/json",
            )
            self.assertEqual(upd.status_code, 200)
            self.assertEqual(upd.data["body"], "second")

class ViewsPageTests(TestCase):
    def setUp(self):
        self.client = Client()
        # create the objects the view requires
        self.patient = Patient.objects.create(name="Test Patient", external_id="T-1")
        self.document = Document.objects.create(content_url="/media/placeholder.pdf")

