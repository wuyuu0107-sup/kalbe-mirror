from django.test import TestCase
from unittest.mock import patch, MagicMock
from dashboard import nav

class TryLabelAnnotationTests(TestCase):
    def test_returns_title_when_present(self):
        mock_annotation = MagicMock()
        mock_annotation.title = "MockTitle"
        mock_annotation.name = None
        with patch("dashboard.nav.Annotation") as MockAnnotation:
            MockAnnotation.objects.filter().only().first.return_value = mock_annotation
            label = nav.try_label_annotation("123")
            self.assertEqual(label, "MockTitle")

    def test_returns_name_when_no_title(self):
        mock_annotation = MagicMock()
        mock_annotation.title = None
        mock_annotation.name = "MockName"
        with patch("dashboard.nav.Annotation") as MockAnnotation:
            MockAnnotation.objects.filter().only().first.return_value = mock_annotation
            label = nav.try_label_annotation("abc")
            self.assertEqual(label, "MockName")

    def test_returns_pk_when_no_title_or_name(self):
        mock_annotation = MagicMock()
        mock_annotation.title = None
        mock_annotation.name = None
        mock_annotation.pk = "999"
        with patch("dashboard.nav.Annotation") as MockAnnotation:
            MockAnnotation.objects.filter().only().first.return_value = mock_annotation
            label = nav.try_label_annotation("999")
            self.assertEqual(label, "#999")

    def test_returns_none_when_no_object_found(self):
        with patch("dashboard.nav.Annotation") as MockAnnotation:
            MockAnnotation.objects.filter().only().first.return_value = None
            label = nav.try_label_annotation("nonexistent")
            self.assertIsNone(label)