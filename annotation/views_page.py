from django.views.generic import TemplateView

class AnnotationTesterPage(TemplateView):
    template_name = "annotation/annotation_test.html"

from django.shortcuts import render, get_object_or_404
from .models import Document

def viewer(request, document_id: int, patient_id: int):
    doc = get_object_or_404(Document, id=document_id)
    pdf_url = doc.content_url or "/media/placeholder.pdf"
    return render(request, "viewer.html", {
        "doc_id": document_id,
        "patient_id": patient_id,
        "pdf_url": pdf_url,
    })
