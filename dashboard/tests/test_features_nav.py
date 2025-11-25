from django.test import TestCase
from unittest.mock import patch, MagicMock
from dashboard import nav
import importlib

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

    def test_returns_none_when_annotation_is_none(self):
        with patch.object(nav, "Annotation", None):
            result = nav.try_label_annotation("123")
            self.assertIsNone(result)

    def test_returns_none_when_exception_raised(self):
        mock_annotation = MagicMock()
        mock_annotation.objects.filter.side_effect = Exception("DB error")
        with patch.object(nav, "Annotation", mock_annotation):
            result = nav.try_label_annotation("err")
            self.assertIsNone(result)

    def test_importerror_sets_annotation_none(self):
        with patch.dict("sys.modules", {"annotation.models": None}):
            
            # Force module reload
            import dashboard.nav as nav_module
            importlib.reload(nav_module)
            self.assertIsNone(nav_module.Annotation)

class LooksLikeIdTests(TestCase):

    def test_digits_are_ids(self):
        """A string of digits should return True"""
        self.assertTrue(nav.looks_like_id("123456"))

    def test_short_non_digits_are_not_ids(self):
        """Short strings with letters should return False"""
        self.assertFalse(nav.looks_like_id("abc"))

    def test_uuid_like_string_returns_true(self):
        """Strings with length >= 8 and hex chars should return True"""
        self.assertTrue(nav.looks_like_id("1a2b3c4d"))

    def test_non_hex_string_returns_false(self):
        """Long string with non-hex chars should return False"""
        self.assertFalse(nav.looks_like_id("1g2h3i4j"))

    def test_long_numeric_string_returns_true(self):
        """Even long numeric strings are considered IDs"""
        self.assertTrue(nav.looks_like_id("1234567890"))

    def test_mixed_valid_hex_with_dash_returns_true(self):
        """Hexadecimal with dash should return True"""
        self.assertTrue(nav.looks_like_id("1a2b-3c4d"))

    def test_mixed_invalid_hex_with_dash_returns_false(self):
        """String with invalid hex letters and dash returns False"""
        self.assertFalse(nav.looks_like_id("1a2b-3c4z"))