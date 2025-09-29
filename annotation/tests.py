from django.test import TestCase, Client
from .models import Patient, Document
from unittest.mock import patch
from authentication.models import User
from rest_framework.test import APIClient
from rest_framework import status

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
