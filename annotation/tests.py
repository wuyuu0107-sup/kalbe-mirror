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


# If your file already declared HAS_COMMENTS earlier, you can reuse it.
try:
    from .models import Comment  # noqa: F401
    HAS_COMMENTS = True
except Exception:
    HAS_COMMENTS = False

class AnnotationCRUDTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.document_id = 1
        self.patient_id = 1
        self.mock_drawing = {
            "type": "drawing",
            "data": [{"tool": "pen", "points": [[10, 10], [20, 20]]}]
        }

        # Create a test user
        self.user = User.objects.create(
            username='testuser',
            password='testpassword',
            email='testuser@example.com',
            is_verified=True
        )

        # Simulate login by setting session data
        session = self.client.session
        session['_auth_user_id'] = str(self.user.user_id)
        session['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
        session.save()

        # Create Patient and Document IDs in the test database
        Patient.objects.create(id=self.patient_id, name="Test Patient")
        Document.objects.create(id=self.document_id)

    def test_invalid_method_on_create_drawing_annotation(self):
        response = self.client.get(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/')
        self.assertEqual(response.status_code, 400)

    def test_not_found_annotation(self):
        response = self.client.get(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/9999/')
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
        # Simulate exception in Annotation.objects.get for GET
        with patch('annotation.views.Annotation.objects.get', side_effect=Exception('Test error')):
            response = self.client.get(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/1/')
            self.assertEqual(response.status_code, 400)
            self.assertIn('Test error', response.content.decode())

    def test_update_drawing_annotation(self):
        # Create annotation
        response = self.client.post(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/', self.mock_drawing, content_type='application/json')
        annotation_id = response.json()["id"]
        updated_drawing = {"type": "drawing", "data": [{"tool": "eraser", "points": [[15, 15], [25, 25]]}]}
        put_response = self.client.put(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/{annotation_id}/', updated_drawing, content_type='application/json')
        self.assertEqual(put_response.status_code, 200)
        self.assertEqual(put_response.json()["drawing"], updated_drawing)

    def test_put_drawing_annotation_exception(self):
        # Simulate exception in Annotation.objects.get for PUT
        updated_drawing = {"type": "drawing", "data": [{"tool": "eraser", "points": [[15, 15], [25, 25]]}]}
        with patch('annotation.views.Annotation.objects.get', side_effect=Exception('Test error')):
            response = self.client.put(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/1/', updated_drawing, content_type='application/json')
            self.assertEqual(response.status_code, 400)
            self.assertIn('Test error', response.content.decode())

    def test_delete_drawing_annotation(self):
        # Create annotation
        response = self.client.post(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/', self.mock_drawing, content_type='application/json')
        annotation_id = response.json()["id"]
        delete_response = self.client.delete(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/{annotation_id}/')
        self.assertEqual(delete_response.status_code, 204)

    def test_delete_drawing_annotation_exception(self):
        # Simulate exception in Annotation.objects.get for DELETE
        with patch('annotation.views.Annotation.objects.get', side_effect=Exception('Test error')):
            response = self.client.delete(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/1/')
            self.assertEqual(response.status_code, 400)
            self.assertIn('Test error', response.content.decode())

    def test_update_nonexistent_annotation(self):
        updated_drawing = {"type": "drawing", "data": [{"tool": "eraser", "points": [[15, 15], [25, 25]]}]}
        response = self.client.put(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/9999/', updated_drawing, content_type='application/json')
        self.assertEqual(response.status_code, 404)

    def test_delete_nonexistent_annotation(self):
        response = self.client.delete(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/9999/')
        self.assertEqual(response.status_code, 404)

    def test_invalid_method_on_drawing_annotation(self):
        response = self.client.post(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/1/')
        self.assertEqual(response.status_code, 400)

    def test_unauthenticated_access(self):
        unauthenticated_client = Client()
        response = unauthenticated_client.get(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/')
        self.assertEqual(response.status_code, 302)  # Redirect to login page


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
        res = self.client.post('/api/v1/annotations/', {
            'document': self.document_id,
            'patient': self.patient_id,
            'label': 'highlight',
            'drawing_data': {'type': 'drawing', 'data': [{'tool': 'pen', 'points': [[10, 10], [20, 20]]}]}
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', res.data)

    def test_list_filter_by_doc_and_patient(self):
        # create two annotations, one for another patient
        a1 = self.client.post('/api/v1/annotations/', {
            'document': self.document_id,
            'patient': self.patient_id,
            'label': 'A1',
            'drawing_data': {'foo': 'bar'}
        }, format='json')
        self.assertEqual(a1.status_code, status.HTTP_201_CREATED)

        pat2 = self.client.post('/api/v1/patients/', {'name': 'Other', 'external_id': 'PAT-002'}, format='json')
        self.assertEqual(pat2.status_code, status.HTTP_201_CREATED)
        a2 = self.client.post('/api/v1/annotations/', {
            'document': self.document_id,
            'patient': pat2.data['id'],
            'label': 'A2',
            'drawing_data': {'foo': 'baz'}
        }, format='json')
        self.assertEqual(a2.status_code, status.HTTP_201_CREATED)

        res = self.client.get(f'/api/v1/annotations/?document={self.document_id}&patient={self.patient_id}')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['label'], 'A1')

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
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

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
        self.assertEqual(res.data["source"], "json")
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