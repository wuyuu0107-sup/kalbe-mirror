import datetime as dt
from django.test import TestCase
from dashboard.services import feature_usage
from unittest import mock

# Services
from dashboard.services.recent_files import get_recent_files

class RecentFileServiceTests(TestCase):

    def test_get_recent_files_sorts_desc_and_limits(self):

        # Fake storage adapter
        class FakeStorage:  
            def __init__(self, objs):
                self.objs = objs
            def list_csv(self):
                return list(self.objs)
            
        sample = [
            {"name":"b.csv","updated_at": dt.datetime(2025,10,7,12,0), "size":1, "path":"b.txt"},
            {"name":"a.csv","updated_at": dt.datetime(2025,10,7,11,0), "size":2, "path":"a.csv"},
            {"name":"d.csv","updated_at":"2025-10-07T10:00:00Z","size":4,"path":"x.csv"},
            
            # Most recent file: c
            {"name":"c.csv","updated_at": dt.datetime(2025,10,7,13,0), "size":3, "path":"c.csv"},
        ]

        with mock.patch("dashboard.services.recent_files.get_storage", return_value=FakeStorage(sample)):
            out = get_recent_files()
        
        self.assertEqual([f["name"] for f in out], ["c.csv", "b.csv", "a.csv", "d.csv"])
        self.assertTrue({"name", "updated_at", "size", "path"}.issubset(out[0].keys()))

class FeatureUsageServiceTests(TestCase):

    @mock.patch("dashboard.services.feature_usage.FeatureUsage.objects.create")
    def test_record_feature_use_handles_exception(self, mock_create):
        
        mock_create.side_effect = Exception("DB down")
        request = mock.Mock()
        request.session = {"user_id": "123"}

        with mock.patch("builtins.print") as mock_print:
            feature_usage.record_feature_use(request, "test-feature")

        mock_print.assert_called_once()
        args, _ = mock_print.call_args
        self.assertIn("[record_feature_use] Error:", args[0])

    @mock.patch("dashboard.services.feature_usage.FeatureUsage.objects.filter")
    def test_get_recent_features_returns_empty_on_exception(self, mock_filter):

        mock_filter.side_effect = Exception("DB down")

        with mock.patch("builtins.print") as mock_print:
            result = feature_usage.get_recent_features(user=mock.Mock())

        self.assertEqual(result, [])
        mock_print.assert_called_once()
        args, _ = mock_print.call_args
        self.assertIn("[get_recent_features] Error:", args[0])

    def test_get_recent_features_returns_empty_if_no_user(self):
        
        result = feature_usage.get_recent_features(user=None)
        self.assertEqual(result, [])