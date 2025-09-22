from django.test import TestCase, Client
from django.urls import reverse
from .models import Annotation, Patient, Document
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

    @patch('annotation.views.get_patients_for_document')
    def test_get_patients_for_document(self, mock_get_patients):
        mock_get_patients.return_value = [{"id": self.patient_id, "name": "John Doe"}]
        response = self.client.get(f'/api/v1/documents/{self.document_id}/patients/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('John Doe', response.content.decode())

    @patch('annotation.views.create_drawing_annotation')
    def test_create_drawing_annotation(self, mock_create_annotation):
        mock_create_annotation.return_value = {"id": 1, "drawing": self.mock_drawing}
        response = self.client.post(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/', self.mock_drawing, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertIn('drawing', response.content.decode())

    @patch('annotation.views.update_drawing_annotation')
    def test_update_drawing_annotation(self, mock_update_annotation):
        updated_drawing = {"type": "drawing", "data": [{"tool": "eraser", "points": [[15, 15], [25, 25]]}]}
        mock_update_annotation.return_value = {"id": 1, "drawing": updated_drawing}
        response = self.client.put(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/1/', updated_drawing, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('eraser', response.content.decode())

    @patch('annotation.views.delete_drawing_annotation')
    def test_delete_drawing_annotation(self, mock_delete_annotation):
        mock_delete_annotation.return_value = True
        response = self.client.delete(f'/api/v1/documents/{self.document_id}/patients/{self.patient_id}/annotations/1/')
        self.assertEqual(response.status_code, 204)
        url = reverse('create_annotation', args=[self.document.id, self.patient.id])
        data = {"field": "diagnosis", "value": "Diabetes"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Annotation.objects.filter(patient=self.patient, field="diagnosis").exists())

    def test_update_annotation(self):
        annotation = Annotation.objects.create(document=self.document, patient=self.patient, field="diagnosis", value="Diabetes")
        url = reverse('update_annotation', args=[self.document.id, self.patient.id, annotation.id])
        data = {"value": "Hypertension"}
        response = self.client.put(url, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        annotation.refresh_from_db()
        self.assertEqual(annotation.value, "Hypertension")

    def test_delete_annotation(self):
        annotation = Annotation.objects.create(document=self.document, patient=self.patient, field="diagnosis", value="Diabetes")
        url = reverse('delete_annotation', args=[self.document.id, self.patient.id, annotation.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Annotation.objects.filter(id=annotation.id).exists())

    def test_get_annotations_after_crud(self):
        # Create annotation
        Annotation.objects.create(document=self.document, patient=self.patient, field="diagnosis", value="Diabetes")
        url = reverse('get_annotations', args=[self.document.id, self.patient.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('Diabetes', response.content.decode())
