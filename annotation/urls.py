# annotation/urls.py
from django.urls import path
from .views import (
    DocumentViewSet, PatientViewSet, AnnotationViewSet, CommentViewSet,
    create_drawing_annotation, drawing_annotation
)
from annotation.views_page import viewer

urlpatterns = [
    # Documents
    path("api/v1/documents/",
         DocumentViewSet.as_view({"get": "list", "post": "create"}),
         name="documents-list-create"),
    path("api/v1/documents/<int:pk>/",
         DocumentViewSet.as_view({"get": "retrieve", "put": "update", "patch": "partial_update"}),
         name="documents-detail"),
    path("api/v1/documents/from-gemini/",
         DocumentViewSet.as_view({"post": "from_gemini"}),
         name="documents-from-gemini"),

    # Patients
    path("api/v1/patients/",
         PatientViewSet.as_view({"get": "list", "post": "create"}),
         name="patients-list-create"),
    path("api/v1/patients/<int:pk>/",
         PatientViewSet.as_view({"get": "retrieve"}),
         name="patients-detail"),

    # Annotations
    path("api/v1/annotations/",
         AnnotationViewSet.as_view({"get": "list", "post": "create"}),
         name="annotations-list-create"),
    path("api/v1/annotations/<int:pk>/",
         AnnotationViewSet.as_view({"get": "retrieve", "put": "update", "delete": "destroy"}),
         name="annotations-detail"),
    path("api/v1/annotations/by_document_patient/",
         AnnotationViewSet.as_view({"get": "by_document_patient"}),
         name="annotations-by-document-patient"),

    # Function-style endpoints under document+patient (used by tests)
    path("api/v1/documents/<int:document_id>/patients/<int:patient_id>/annotations/",
         create_drawing_annotation,
         name="create_drawing_annotation"),
    path("api/v1/documents/<int:document_id>/patients/<int:patient_id>/annotations/<int:annotation_id>/",
         drawing_annotation,
         name="drawing_annotation"),

    # Comments
    path("api/v1/comments/",
         CommentViewSet.as_view({"get": "list", "post": "create"}),
         name="comments-list-create"),
    path("api/v1/comments/<int:pk>/",
         CommentViewSet.as_view({"get": "retrieve", "put": "update", "delete": "destroy"}),
         name="comments-detail"),

    # Viewer page
    path("viewer/<int:document_id>/<int:patient_id>/", viewer, name="viewer"),
]
