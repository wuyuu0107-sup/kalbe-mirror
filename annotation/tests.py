from django.test import TestCase, Client
from .models import Patient, Document
from unittest.mock import patch

class AnnotationCRUDTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.document_id = 1
        self.patient_id = 1
        self.mock_drawing = {
            "type": "drawing",
            "data": [{"tool": "pen", "points": [[10, 10], [20, 20]]}]
        }

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
