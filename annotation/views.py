# annotation/views.py

import os, re, json

from django.http import JsonResponse, HttpResponseNotFound, HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from rest_framework import viewsets, mixins, filters, status
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import SessionAuthentication, BasicAuthentication

from django_filters.rest_framework import DjangoFilterBackend

import google.generativeai as genai

from .models import Document, Patient, Annotation, Comment
from .serializers import DocumentSerializer, PatientSerializer, AnnotationSerializer, CommentSerializer


# ---------- Document API ----------
class DocumentViewSet(mixins.CreateModelMixin,
                      mixins.RetrieveModelMixin,
                      mixins.UpdateModelMixin,
                      mixins.ListModelMixin,
                      viewsets.GenericViewSet):

    queryset = Document.objects.all().order_by('-created_at')
    serializer_class = DocumentSerializer

    @action(detail=False, methods=['post'], url_path='from-gemini')
    def from_gemini(self, request):
        f = request.FILES.get('file')
        if not f:
            return Response({"error": "Upload a PDF as 'file'."}, status=400)

        api_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
        if not api_key:
            return Response({"error": "GEMINI_API_KEY not set"}, status=500)

        # Configure Gemini
        genai.configure(
            api_key=api_key,
            client_options={"api_endpoint": "https://generativelanguage.googleapis.com"}
        )

        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            pdf_bytes = f.read()
            resp = model.generate_content(
                [
                    "Return ONLY JSON in the target schema.",
                    {"mime_type": "application/pdf", "data": pdf_bytes}
                ],
                generation_config={"temperature": 0}
            )
            text = (resp.text or "").strip()
            text = re.sub(r"^```json\s*", "", text, flags=re.M)
            text = re.sub(r"^```", "", text, flags=re.M)
            text = re.sub(r"\s*```$", "", text)

            try:
                structured = json.loads(text)
            except Exception:
                m = re.search(r"\{.*\}\s*$", text, flags=re.S)
                structured = json.loads(m.group(0)) if m else {}

            file_path = default_storage.save(f"uploads/{f.name}", ContentFile(pdf_bytes))

            doc = Document.objects.create(
                source='pdf',
                content_url=default_storage.url(file_path),
                payload_json=structured,
                meta={'from': 'gemini'}
            )
            return Response(DocumentSerializer(doc).data, status=201)

        except Exception as e:
            return Response({"error": str(e)}, status=502)


# ---------- Patient API ----------
class PatientViewSet(mixins.CreateModelMixin,
                     mixins.RetrieveModelMixin,
                     mixins.ListModelMixin,
                     viewsets.GenericViewSet):

    queryset = Patient.objects.all().order_by('id')
    serializer_class = PatientSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'external_id']


# ---------- Annotation API ----------
class AnnotationViewSet(viewsets.ModelViewSet):
    queryset = Annotation.objects.select_related('document', 'patient').all().order_by('-created_at')
    serializer_class = AnnotationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['document', 'patient']

    @action(detail=False, methods=['get'])
    def by_document_patient(self, request):
        doc_id = request.query_params.get('document')
        pat_id = request.query_params.get('patient')
        qs = self.get_queryset()
        if doc_id:
            qs = qs.filter(document_id=doc_id)
        if pat_id:
            qs = qs.filter(patient_id=pat_id)
        page = self.paginate_queryset(qs)
        if page is not None:
            ser = self.get_serializer(page, many=True)
            return self.get_paginated_response(ser.data)
        ser = self.get_serializer(qs, many=True)
        return Response(ser.data, status=status.HTTP_200_OK)


# ---------- Comment API ----------
class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.select_related('document', 'patient').all().order_by('-created_at')
    serializer_class = CommentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['document', 'patient']


# ---------- Function-style Endpoints ----------
@api_view(['POST'])
def create_drawing_annotation(request, document_id, patient_id):
    try:
        body = json.loads(request.body.decode('utf-8'))
        annotation = Annotation.objects.create(
            document_id=document_id,
            patient_id=patient_id,
            drawing_data=body
        )
        return JsonResponse({
            "id": annotation.id,
            "drawing": annotation.drawing_data,
            "created": annotation.created_at,
            "updated": annotation.updated_at
        }, status=201)
    except Exception as e:
        return HttpResponseBadRequest(str(e))


@api_view(['GET', 'PUT', 'DELETE'])
def drawing_annotation(request, document_id, patient_id, annotation_id):
    try:
        annotation = Annotation.objects.get(
            id=annotation_id, document_id=document_id, patient_id=patient_id
        )
    except Annotation.DoesNotExist:
        return HttpResponseNotFound("Annotation not found")

    if request.method == "GET":
        return JsonResponse({
            "id": annotation.id,
            "drawing": annotation.drawing_data,
            "created": annotation.created_at,
            "updated": annotation.updated_at
        })
    elif request.method == "PUT":
        try:
            body = json.loads(request.body.decode('utf-8'))
            annotation.drawing_data = body
            annotation.save()
            return JsonResponse({"id": annotation.id, "drawing": annotation.drawing_data})
        except Exception as e:
            return HttpResponseBadRequest(str(e))
    elif request.method == "DELETE":
        annotation.delete()
        return HttpResponse(status=204)
    

