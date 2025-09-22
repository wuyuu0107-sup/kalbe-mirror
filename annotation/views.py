from django.http import JsonResponse, HttpResponseNotFound, HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Document, Patient, Annotation

def get_patients_for_document(request, document_id):
    if request.method == "GET":
        try:
            patients = Patient.objects.filter(document_id=document_id)
            data = [{"id": p.id, "name": p.name} for p in patients]
            return JsonResponse(data, safe=False)
        except Exception as e:
            return HttpResponseBadRequest(str(e))
    return HttpResponseBadRequest("Invalid method")

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
