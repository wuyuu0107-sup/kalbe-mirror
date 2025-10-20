import os, re, json, time, mimetypes

from django.http import JsonResponse, HttpResponseNotFound, HttpResponse, HttpResponseBadRequest
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

from rest_framework import viewsets, mixins, filters, status
from rest_framework.response import Response
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission
from rest_framework.authentication import SessionAuthentication, BasicAuthentication

from django_filters.rest_framework import DjangoFilterBackend

import google.generativeai as genai
from supabase import create_client, Client

from .models import Document, Patient, Annotation, Comment
from .serializers import DocumentSerializer, PatientSerializer, AnnotationSerializer, CommentSerializer



# Optional: reuse your normalizer if available
try:
    from ocr.views import normalize_payload, order_sections  # if you want same schema/ordering here
except Exception:
    normalize_payload = lambda x: x
    order_sections = lambda x: x

def _get_supabase() -> Client | None:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if url and key:
        return create_client(url, key)
    return None

def _storage_upload_bytes(supabase: Client, bucket: str, path: str, data: bytes, content_type: str = "application/octet-stream"):
    return supabase.storage.from_(bucket).upload(
        path=path,
        file=data,
        file_options={"contentType": content_type, "upsert": "true"},
    )

def _storage_public_or_signed_url(supabase: Client, bucket: str, path: str, ttl_seconds: int = 7*24*3600) -> str | None:
    s = supabase.storage.from_(bucket)
    try:
        pub = s.get_public_url(path)
        if isinstance(pub, str):
            return pub
        if isinstance(pub, dict):
            return pub.get("publicURL") or pub.get("public_url")
    except Exception:
        pass
    try:
        signed = s.create_signed_url(path, ttl_seconds)
        if isinstance(signed, dict):
            return signed.get("signedURL") or signed.get("signed_url")
    except Exception:
        pass
    return None

def _safe_ct(filename: str, fallback: str = "application/octet-stream") -> str:
    return mimetypes.guess_type(filename)[0] or fallback

def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


from supabase import create_client, Client

def _get_supabase() -> Client | None:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # server-only key
    if not url or not key:
        return None
    return create_client(url, key)

def _upload_drawing_json(supabase: Client, bucket: str, path: str, data: dict) -> str | None:
    try:
        b = json.dumps(data, ensure_ascii=False, separators=(",", ":"), indent=2).encode("utf-8")
        supabase.storage.from_(bucket).upload(path=path, file=b, file_options={
            "contentType": "application/json",
            "upsert": "true",
        })
        # Prefer public URL; fallback to a signed URL
        try:
            pub = supabase.storage.from_(bucket).get_public_url(path)
            if isinstance(pub, str):
                return pub
            if isinstance(pub, dict):
                return pub.get("publicURL") or pub.get("public_url")
        except Exception:
            pass
        signed = supabase.storage.from_(bucket).create_signed_url(path, 7 * 24 * 3600)
        if isinstance(signed, dict):
            return signed.get("signedURL") or signed.get("signed_url")
        return signed
    except Exception:
        return None

class IsResearcher(BasePermission):
    """DRF permission: allow access only to users who have 'researcher' role."""

    message = 'user must have researcher role'

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not user or not getattr(user, 'is_authenticated', False):
            return False
        roles = getattr(user, 'roles', []) or []
        # roles may be stored as list of strings
        return 'researcher' in roles

class DocumentViewSet(mixins.CreateModelMixin,
                      mixins.RetrieveModelMixin,
                      mixins.UpdateModelMixin,
                      mixins.ListModelMixin,
                      viewsets.GenericViewSet):

    queryset = Document.objects.all().order_by('-created_at')
    serializer_class = DocumentSerializer
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]


    @action(detail=False, methods=['post'], url_path='from-gemini', permission_classes=[AllowAny])
    def from_gemini(self, request):
        f = request.FILES.get('file')
        if not f:
            return Response({"error": "Upload a PDF as 'file'."}, status=400)

        api_key = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
        if not api_key:
            return Response({"error": "GEMINI_API_KEY not set"}, status=500)

        genai.configure(
            api_key=api_key,
            client_options={"api_endpoint": "https://generativelanguage.googleapis.com"}
        )

        supabase = _get_supabase()
        BUCKET = os.getenv("SUPABASE_BUCKET", "ocr")

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
            text = re.sub(r"(?:\s*```)+\Z", "", text)

            try:
                structured = json.loads(text)
            except Exception:
                m = re.search(r"\{.*\}\s*$", text, flags=re.S)
                structured = json.loads(m.group(0)) if m else {}

            # optional: normalize + order to match your OCR pipeline
            structured = order_sections(normalize_payload(structured))

            # local dev fallback (still okay to keep)
            file_path = default_storage.save(f"uploads/{f.name}", ContentFile(pdf_bytes))
            local_url = default_storage.url(file_path)

            # ---- Supabase Storage uploads ----
            storage_pdf_url = None
            storage_json_url = None
            if supabase:
                ts = int(time.time())
                safe = _safe_name(f.name)
                pdf_path = f"docs/{ts}_{safe}"
                json_path = pdf_path.rsplit(".", 1)[0] + ".json"

                _storage_upload_bytes(supabase, BUCKET, pdf_path, pdf_bytes, _safe_ct(f.name, "application/pdf"))
                storage_pdf_url = _storage_public_or_signed_url(supabase, BUCKET, pdf_path)

                json_bytes = json.dumps(structured, ensure_ascii=False, separators=(",", ":"), indent=2).encode("utf-8")
                _storage_upload_bytes(supabase, BUCKET, json_path, json_bytes, "application/json")
                storage_json_url = _storage_public_or_signed_url(supabase, BUCKET, json_path)

            doc = Document.objects.create(
                source='pdf',
                content_url=storage_pdf_url or local_url,
                payload_json=structured,
                meta={
                    'from': 'gemini',
                    'local_fallback_url': local_url,
                    'storage_pdf_url': storage_pdf_url,
                    'storage_json_url': storage_json_url,
                }
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
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsAuthenticated]

    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'external_id']


# ---------- Annotation API ----------
class AnnotationViewSet(viewsets.ModelViewSet):
    queryset = Annotation.objects.select_related('document', 'patient').all().order_by('-created_at')
    serializer_class = AnnotationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['document', 'patient']
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsResearcher]


    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
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
    authentication_classes = [SessionAuthentication, BasicAuthentication]
    permission_classes = [IsResearcher]



@api_view(['POST'])
@permission_classes([IsResearcher])
@authentication_classes([SessionAuthentication, BasicAuthentication])
def create_drawing_annotation(request, document_id, patient_id):
    try:
        body = json.loads(request.body.decode('utf-8'))
        annotation = Annotation.objects.create(
            document_id=document_id,
            patient_id=patient_id,
            drawing_data=body
        )

        storage_url = None
        supabase = _get_supabase()
        if supabase:
            bucket = os.getenv("SUPABASE_BUCKET_DRAWINGS", "drawings")
            ts = int(time.time())
            path = f"{document_id}/{patient_id}/{annotation.id}-{ts}.json"
            storage_url = _upload_drawing_json(supabase, bucket, path, body)

        return JsonResponse({
            "id": annotation.id,
            "drawing": annotation.drawing_data,
            "storage_url": storage_url,   # <- handy to return to client
            "created": annotation.created_at,
            "updated": annotation.updated_at
        }, status=201)
    except Exception as e:
        return HttpResponseBadRequest(str(e))


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsResearcher])
@authentication_classes([SessionAuthentication, BasicAuthentication])
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

            storage_url = None
            supabase = _get_supabase()
            if supabase:
                bucket = os.getenv("SUPABASE_BUCKET_DRAWINGS", "drawings")
                ts = int(time.time())
                path = f"{document_id}/{patient_id}/{annotation.id}-{ts}.json"
                storage_url = _upload_drawing_json(supabase, bucket, path, body)

            return JsonResponse({
                "id": annotation.id,
                "drawing": annotation.drawing_data,
                "storage_url": storage_url,
                "updated": annotation.updated_at
            })
        except Exception as e:
            return HttpResponseBadRequest(str(e))

    elif request.method == "DELETE":
        annotation.delete()
        return HttpResponse(status=204)