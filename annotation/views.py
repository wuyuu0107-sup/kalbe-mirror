from django.http import JsonResponse, HttpResponseNotFound, HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication, BasicAuthentication
import json
from .models import Annotation

@login_required
@csrf_exempt
def create_drawing_annotation(request, document_id, patient_id):
    if request.method == "POST":
        try:
            body = json.loads(request.body)
            annotation = Annotation.objects.create(
                document_id=document_id,
                patient_id=patient_id,
                drawing_data=body
            )
            return JsonResponse({"id": annotation.id, "drawing": annotation.drawing_data, "created": annotation.created_at, "updated": annotation.updated_at}, status=201)
        except Exception as e:
            return HttpResponseBadRequest(str(e))
    return HttpResponseBadRequest("Invalid method")

@login_required
@csrf_exempt
def drawing_annotation(request, document_id, patient_id, annotation_id):
    if request.method == "GET":
        try:
            annotation = Annotation.objects.get(id=annotation_id, document_id=document_id, patient_id=patient_id)
            return JsonResponse({"id": annotation.id, "drawing": annotation.drawing_data, "created": annotation.created_at, "updated": annotation.updated_at})
        except Annotation.DoesNotExist:
            return HttpResponseNotFound("Annotation not found")
        except Exception as e:
            return HttpResponseBadRequest(str(e))

    elif request.method == "PUT":
        try:
            body = json.loads(request.body)
            annotation = Annotation.objects.get(id=annotation_id, document_id=document_id, patient_id=patient_id)
            annotation.drawing_data = body
            annotation.save()
            return JsonResponse({"id": annotation.id, "drawing": annotation.drawing_data})
        except Annotation.DoesNotExist:
            return HttpResponseNotFound("Annotation not found")
        except Exception as e:
            return HttpResponseBadRequest(str(e))

    elif request.method == "DELETE":
        try:
            annotation = Annotation.objects.get(id=annotation_id, document_id=document_id, patient_id=patient_id)
            annotation.delete()
            return HttpResponse(status=204)
        except Annotation.DoesNotExist:
            return HttpResponseNotFound("Annotation not found")
        except Exception as e:
            return HttpResponseBadRequest(str(e))

    return HttpResponseBadRequest("Invalid method")

from rest_framework import viewsets, mixins, filters, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend

from .models import Document, Patient, Annotation
from .serializers import DocumentSerializer, PatientSerializer, AnnotationSerializer


class DocumentViewSet(mixins.CreateModelMixin,
                      mixins.RetrieveModelMixin,
                      viewsets.GenericViewSet):
    """
    Minimal: OCR service POSTs here to create a Document record.
    """
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    queryset = Document.queryset = Document.objects.all().order_by('-created_at')
    serializer_class = DocumentSerializer
    
    @action(detail=False, methods=['post'], url_path='from-gemini')
    def from_gemini(self, request):
        """
        POST /api/v1/documents/from-gemini/
        form-data:
          - file: PDF
        Returns: created Document (payload_json filled with Gemini's structured JSON)
        """
        f = request.FILES.get('file')
        if not f:
            return Response({"error": "Upload a PDF as 'file'."}, status=400)

        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            return Response({"error": "GEMINI_API_KEY not set"}, status=500)

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash-latest")

            pdf_bytes = f.read()
            resp = model.generate_content(
                ["Return ONLY JSON in the target schema.",
                 {"mime_type": "application/pdf", "data": pdf_bytes}],
                generation_config={"temperature": 0}
            )

            text = (resp.text or "").strip()
            # ✅ Python regex, not JS
            text = re.sub(r"^```json\s*", "", text, flags=re.M)
            text = re.sub(r"^```\s*", "", text, flags=re.M)
            text = re.sub(r"\s*```$", "", text)

            try:
                structured = json.loads(text)
            except Exception:
                # last-resort: extract the last {...} block
                m = re.search(r"\{.*\}\s*$", text, flags=re.S)
                structured = json.loads(m.group(0)) if m else {}

            doc = Document.objects.create(
                source='json',
                payload_json=structured,
                meta={'from': 'gemini'}
            )
            return Response(DocumentSerializer(doc).data, status=201)

        except Exception as e:
            return Response({"error": str(e)}, status=502)


class PatientViewSet(mixins.CreateModelMixin,
                     mixins.RetrieveModelMixin,
                     mixins.ListModelMixin,
                     viewsets.GenericViewSet):
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    queryset = Patient.objects.all().order_by('id')
    serializer_class = PatientSerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'external_id']


class AnnotationViewSet(viewsets.ModelViewSet):
    """
    Full CRUD + filtering by document & patient.
    """
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    queryset = Annotation.objects.select_related('document', 'patient').all().order_by('-created_at')
    serializer_class = AnnotationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['document', 'patient']

    @action(detail=False, methods=['get'])
    def by_document_patient(self, request):
        """
        Convenience endpoint:
        GET /api/v1/annotations/by_document_patient?document=<id>&patient=<id>
        """
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
