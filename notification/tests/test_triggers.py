# notification/tests/test_triggers.py
from unittest.mock import patch
from django.test import TestCase
from notification import triggers

@patch("notification.triggers.sse_send")
class TriggerTests(TestCase):
    def test_notify_ocr_completed_calls_sse(self, m):
        triggers.notify_ocr_completed("sess1", path="csvs/a.csv", size=123, job_id="job1")
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertEqual(args[0], "sess1")
        self.assertEqual(args[1], "ocr.completed")
        self.assertEqual(kwargs["data"]["path"], "csvs/a.csv")
        self.assertEqual(kwargs["job_id"], "job1")

    def test_notify_ocr_failed_calls_sse(self, m):
        triggers.notify_ocr_failed("sess1", path="csvs/a.csv", reason="blurred image", job_id="job1")
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertEqual(args[0], "sess1")
        self.assertEqual(args[1], "ocr.failed")
        self.assertEqual(kwargs["data"]["path"], "csvs/a.csv")
        self.assertEqual(kwargs["data"]["reason"], "blurred image")
        self.assertEqual(kwargs["job_id"], "job1")
    
    def test_notify_chat_reply_calls_sse(self, m):
        triggers.notify_chat_reply("sess1", job_id="job1")
        m.assert_called_once()
        args, kwargs = m.call_args
        self.assertEqual(args[0], "sess1")
        self.assertEqual(args[1], "chat.reply")
        self.assertEqual(kwargs["job_id"], "job1")


