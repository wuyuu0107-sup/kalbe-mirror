from django.urls import path
from . import views
from .views import DocumentViewSet, PatientViewSet, AnnotationViewSet
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'api/v1/documents', DocumentViewSet, basename='documents')
router.register(r'api/v1/patients', PatientViewSet, basename='patients')
router.register(r'api/v1/annotations', AnnotationViewSet, basename='annotations')

urlpatterns = [
    path('api/v1/documents/<int:document_id>/patients/<int:patient_id>/annotations/', views.create_drawing_annotation, name='create_drawing_annotation'),
    path('api/v1/documents/<int:document_id>/patients/<int:patient_id>/annotations/<int:annotation_id>/', views.drawing_annotation, name='drawing_annotation'),
]
