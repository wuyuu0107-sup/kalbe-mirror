import json
import threading
import time
from django.test import TestCase, override_settings
from django.urls import reverse

from notification import sse

class SSETtests(TestCase):
    def test_requires_session_id(self):
        url = reverse("sse-subscribe")
        r = self.client.get(url)
        self.assertEqual(r.status_code, 400)

    def test_streams_event_for_session(self):
        url = reverse("sse-subscribe") + "?session_id=testsess"
        r = self.client.get(url)

        # Should be an SSE stream
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "text/event-stream")

        # The first chunk is the retry hint; consume it
        g = iter(r.streaming_content)
        first = next(g).decode() if isinstance(next(iter([b""])), bytes) else next(g)
        self.assertIn("retry:", first)

        # Enqueue an event in another thread (so the generator has something to yield)
        def push():
            time.sleep(0.05)
            sse.sse_send("testsess", "ocr.completed", data={"path": "csvs/a.csv"})

        t = threading.Thread(target=push, daemon=True)
        t.start()

        # Next chunk should contain our event as JSON
        second = next(g).decode() if isinstance(next(iter([b""])), bytes) else next(g)
        self.assertTrue(second.startswith("data: "))
        payload = json.loads(second[len("data: "):].strip())
        self.assertEqual(payload["type"], "ocr.completed")
        self.assertEqual(payload["data"]["path"], "csvs/a.csv")

        t.join(timeout=1)

    def test_multiple_clients_receive_same_event(self):
        url = reverse("sse-subscribe") + "?session_id=multi"
        r1 = self.client.get(url)
        r2 = self.client.get(url)

        g1 = iter(r1.streaming_content); _ = next(g1)  # retry
        g2 = iter(r2.streaming_content); _ = next(g2)

        sse.sse_send("multi", "chat.reply", data={"message_id": "m1"})

        chunk1 = next(g1).decode() if isinstance(next(iter([b""])), bytes) else next(g1)
        chunk2 = next(g2).decode() if isinstance(next(iter([b""])), bytes) else next(g2)

        self.assertIn("chat.reply", chunk1)
        self.assertIn("chat.reply", chunk2)