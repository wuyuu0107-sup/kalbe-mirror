import datetime as dt
from unittest import TestCase, mock

# Services
from dashboard.services.recent_files import get_recent_files

class RecentFileServiceTests(TestCase):

    def test_get_recent_files_sorts_desc_and_limits(self):

        # Fask storage adapter
        class FakeStorage:  
            def __init__(self, objs):
                self.objs = objs
            def list_csv(self, limit=10):
                return list(self.objs)
            
        sample = [
            {"name":"b.csv","updated_at": dt.datetime(2025,10,7,12,0), "size":1, "path":"b.txt"},
            {"name":"a.csv","updated_at": dt.datetime(2025,10,7,11,0), "size":2, "path":"a.csv"},
            
            # Most recent file: c
            {"name":"c.csv","updated_at": dt.datetime(2025,10,7,13,0), "size":3, "path":"c.csv"},
        ]

        with mock.patch("dashboard.services.recent_files.get_storage", return_value=FakeStorage(sample)):
            out = get_recent_files()
        
        self.assertEqual([f["name"] for f in out], ["c.csv", "b.csv", "a.csv"])
        self.assertTrue({"name", "updated_at", "size", "path"}.issubset(out[0].keys()))