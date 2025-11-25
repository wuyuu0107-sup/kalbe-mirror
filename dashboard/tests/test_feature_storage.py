from django.test import TestCase
from unittest.mock import patch, MagicMock
import os
import importlib
import dashboard.storage as storage_module

class SupabaseCSVStorageTests(TestCase):
    def setUp(self):
        self.url = "https://fake.supabase.io"
        self.key = "fake-key"

    # POSITIVE TESTS

    def test_null_storage_list_csv_returns_empty(self):
        """Positive: NullStorage should always return an empty list"""
        s = storage_module.NullStorage()
        self.assertEqual(s.list_csv(), [])

    @patch("dashboard.storage.create_client")
    def test_list_csv_returns_sorted_output(self, mock_create_client):
        """Positive: SupabaseCSVStorage.list_csv should return sorted CSV objects with path"""
        fake_storage = MagicMock()
        fake_storage.list.return_value = [
            {"name": "b.csv", "size": 2},
            {"name": "a.csv", "size": 1},
        ]
        fake_cli = MagicMock()
        mock_create_client.return_value = fake_cli

        s = storage_module.SupabaseCSVStorage(self.url, self.key)
        s._storage = fake_storage  # inject mocked storage

        result = s.list_csv()
        self.assertEqual(result[0]["name"], "b.csv")
        self.assertEqual(result[1]["name"], "a.csv")
        self.assertTrue(all("path" in o for o in result))

    @patch("dashboard.storage.create_client")
    def test_list_csv_skips_empty_name(self, mock_create_client):
        """Positive: SupabaseCSVStorage.list_csv should skip entries with empty names"""
        mock_cli = MagicMock()
        mock_storage = MagicMock()
        mock_cli.storage.from_.return_value = mock_storage
        mock_create_client.return_value = mock_cli

        mock_storage.list.return_value = [
            {"name": "", "size": 123},      # invalid entry, should be skipped
            {"name": "valid.csv", "size": 456},  # valid entry
        ]

        s = storage_module.SupabaseCSVStorage(self.url, self.key)
        s._storage = mock_storage

        result = s.list_csv()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "valid.csv")

    # NEGATIVE TESTS

    def test_init_raises_if_create_client_missing(self):
        """Negative: Should raise RuntimeError if create_client is not available"""
        with patch.object(storage_module, "create_client", None):
            with self.assertRaises(RuntimeError):
                storage_module.SupabaseCSVStorage(self.url, self.key)

class GetStorageEdgeCasesTests(TestCase):
    
    # EDGE TESTS

    @patch.dict(os.environ, {"SUPABASE_URL": "url", "SUPABASE_SERVICE_KEY": "key"})
    @patch("dashboard.storage.SupabaseCSVStorage", side_effect=Exception("fail"))
    def test_get_storage_raises_exception_returns_null(self, mock_storage):
        """Edge: get_storage() should return NullStorage if SupabaseCSVStorage instantiation fails"""
        res = storage_module.get_storage()
        self.assertIsInstance(res, storage_module.NullStorage)

    def test_get_storage_no_env_vars_triggers_final_return(self):
        """Edge: get_storage() should return NullStorage when no env vars are set"""
        with patch.dict("os.environ", {}, clear=True):
            res = storage_module.get_storage()
            self.assertIsInstance(res, storage_module.NullStorage)

    def test_module_level_constants_are_evaluated(self):
        """Edge: Reloading module should evaluate BUCKET and FOLDER defaults"""
        if "dashboard.storage" in importlib.sys.modules:
            del importlib.sys.modules["dashboard.storage"]
        storage_module_reloaded = importlib.import_module("dashboard.storage")
        self.assertTrue(hasattr(storage_module_reloaded, "BUCKET"))
        self.assertTrue(hasattr(storage_module_reloaded, "FOLDER"))