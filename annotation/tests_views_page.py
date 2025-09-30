# annotation/tests_views_page.py
from django.test import TestCase, RequestFactory, override_settings
from django.http import HttpRequest
from annotation.views_page import AnnotationTesterPage, viewer
from annotation.models import Document

# Use in-memory templates so render() works without touching the filesystem
TEMPLATES_OVERRIDE = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "APP_DIRS": False,
    "OPTIONS": {
        "loaders": [
            ("django.template.loaders.locmem.Loader", {
                "annotation/annotation_test.html": "Annotation Tester OK",
                "viewer.html": "doc={{ doc_id }}; patient={{ patient_id }}; url={{ pdf_url }}"
            })
        ],
        "context_processors": [
            "django.template.context_processors.request",
        ],
    },
}]


@override_settings(TEMPLATES=TEMPLATES_OVERRIDE)
class ViewsPageTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_annotation_tester_page_renders(self):
        req: HttpRequest = self.rf.get("/fake/annotation/test/")
        resp = AnnotationTesterPage.as_view()(req)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Annotation Tester OK", resp.content)

    def test_viewer_uses_document_content_url(self):
        # Document with explicit URL
        doc = Document.objects.create(source="pdf", content_url="/media/some.pdf")
        req = self.rf.get("/fake/viewer/")
        resp = viewer(req, document_id=doc.id, patient_id=42)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"doc=%d" % doc.id, resp.content)
        self.assertIn(b"patient=42", resp.content)
        self.assertIn(b"url=/media/some.pdf", resp.content)

    def test_viewer_falls_back_to_placeholder_when_no_content_url(self):
        # Document without content_url should fallback
        doc = Document.objects.create(source="pdf", content_url="")
        req = self.rf.get("/fake/viewer/")
        resp = viewer(req, document_id=doc.id, patient_id=7)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"url=/media/placeholder.pdf", resp.content)
