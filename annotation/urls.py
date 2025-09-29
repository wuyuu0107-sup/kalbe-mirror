# annotation/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DocumentViewSet, PatientViewSet, AnnotationViewSet, create_drawing_annotation, drawing_annotation, CommentViewSet

router = DefaultRouter()
router.register(r'api/v1/documents', DocumentViewSet, basename='documents')
router.register(r'api/v1/patients', PatientViewSet, basename='patients')
router.register(r'api/v1/annotations', AnnotationViewSet, basename='annotations')
router.register(r'api/v1/comments', CommentViewSet, basename='comments')   # NEW

urlpatterns = [
    path('api/v1/documents/<int:document_id>/patients/<int:patient_id>/annotations/', create_drawing_annotation, name='create_drawing_annotation'),
    path('api/v1/documents/<int:document_id>/patients/<int:patient_id>/annotations/<int:annotation_id>/', drawing_annotation, name='drawing_annotation'),
    path('', include(router.urls)),
]
