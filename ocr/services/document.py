# ocr/services/document.py
from typing import Dict, Any, Tuple

from annotation.models import Document
from patient.models import Patient   # 👈 import from the real app


class DocumentService:
    
    SECTION_ORDER = [
        "DEMOGRAPHY",
        "MEDICAL_HISTORY",
        "VITAL_SIGNS",
        "SEROLOGY",
        "URINALYSIS",
        "HEMATOLOGY",
        "CLINICAL_CHEMISTRY",
    ]
    
    def create_document_and_patient(
        self,
        ordered_data: Dict[str, Any],
        pdf_url: str,
        supabase_urls: Dict[str, str],
        local_pdf_url: str
    ) -> Tuple[Document, Patient]:
        doc = Document.objects.create(
            source="pdf",
            content_url=pdf_url,
            payload_json=ordered_data,
            meta={
                "from": "gemini_2_5",
                "local_fallback_url": local_pdf_url,
                "storage_pdf_url": supabase_urls["pdf_url"],
                "storage_json_url": supabase_urls["json_url"],
                "section_order": self.SECTION_ORDER,
            },
        )
        
        # subject_initials is required, external_id no longer exists
        pat = Patient.objects.create(
            name="OCR Patient",
            subject_initials="OCR",
        )
        
        return doc, pat
