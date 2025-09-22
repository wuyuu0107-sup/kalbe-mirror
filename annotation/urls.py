from django.urls import path
from . import views

urlpatterns = [
    path('api/v1/documents/<int:document_id>/patients/', views.get_patients_for_document, name='get_patients_for_document'),
    path('api/v1/documents/<int:document_id>/patients/<int:patient_id>/annotations/', views.create_drawing_annotation, name='create_drawing_annotation'),
    path('api/v1/documents/<int:document_id>/patients/<int:patient_id>/annotations/<int:annotation_id>/', views.drawing_annotation, name='drawing_annotation'),
]
