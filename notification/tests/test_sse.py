import json
import threading
import time
from django.test import TestCase
from django.urls import reverse
from notification import sse

SLEEP = 0.05  # small delay so the server-side generator is active before we push

class SSETtests(TestCase):
    def setUp(self):
        self.base = reverse("sse-subscribe")

    @staticmethod
    def _read_chunk(gen):
        """Read one chunk from a streaming generator and normalize to str."""
        chunk = next(gen)
        return chunk.decode() if isinstance(chunk, (bytes, bytearray)) else chunk

    def _read_retry(self, gen):
        """Consume the initial retry hint line."""
        first = self._read_chunk(gen)
        self.assertIn("retry:", first)
        return first

    def _read_event(self, gen):
        """Read a 'data: ...' line and parse its JSON payload."""
        line = self._read_chunk(gen)
        self.assertTrue(line.startswith("data: "))
        return json.loads(line[len("data: "):].strip())

    def test_requires_session_id(self):
        r = self.client.get(self.base)
        self.assertEqual(r.status_code, 400)

    def test_streams_event_for_session(self):
        r = self.client.get(f"{self.base}?session_id=testsess")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "text/event-stream")

        g = iter(r.streaming_content)
        self._read_retry(g)

        def push():
            time.sleep(SLEEP)
            sse.sse_send("testsess", "ocr.completed", data={"path": "csvs/a.csv"})

        t = threading.Thread(target=push, daemon=True)
        t.start()

        payload = self._read_event(g)
        self.assertEqual(payload["type"], "ocr.completed")
        self.assertEqual(payload["data"]["path"], "csvs/a.csv")

        t.join(timeout=1)

    def test_multiple_clients_receive_same_event(self):
        r1 = self.client.get(f"{self.base}?session_id=multi")
        r2 = self.client.get(f"{self.base}?session_id=multi")

        g1 = iter(r1.streaming_content)
        g2 = iter(r2.streaming_content)
        self._read_retry(g1)
        self._read_retry(g2)

        def push():
            time.sleep(SLEEP)
            sse.sse_send("multi", "chat.reply", data={"message_id": "m1"})

        t = threading.Thread(target=push, daemon=True)
        t.start()

        # Read both events
        ev1 = self._read_event(g1)
        ev2 = self._read_event(g2)
        t.join(timeout=1)

        self.assertEqual(ev1["type"], "chat.reply")
        self.assertEqual(ev2["type"], "chat.reply")
        self.assertEqual(ev1["data"]["message_id"], "m1")
        self.assertEqual(ev2["data"]["message_id"], "m1")

    def test_clients_receive_different_event(self):
        r1 = self.client.get(f"{self.base}?session_id=s1")
        r2 = self.client.get(f"{self.base}?session_id=s2")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)

        g1 = iter(r1.streaming_content)
        g2 = iter(r2.streaming_content)
        self._read_retry(g1)
        self._read_retry(g2)

        def push_s1():
            time.sleep(SLEEP)
            sse.sse_send("s1", "chat.reply", data={"message_id": "m1", "session": "s1"})

        def push_s2():
            time.sleep(SLEEP)
            sse.sse_send("s2", "chat.reply", data={"message_id": "m2", "session": "s2"})

        t1 = threading.Thread(target=push_s1, daemon=True)
        t2 = threading.Thread(target=push_s2, daemon=True)
        t1.start()
        t2.start()

        ev1 = self._read_event(g1)
        ev2 = self._read_event(g2)

        t1.join(timeout=1)
        t2.join(timeout=1)

        # Types
        self.assertEqual(ev1["type"], "chat.reply")
        self.assertEqual(ev2["type"], "chat.reply")

        # Session scoping
        self.assertEqual(ev1["data"]["message_id"], "m1")
        self.assertEqual(ev1["data"]["session"], "s1")
        self.assertEqual(ev2["data"]["message_id"], "m2")
        self.assertEqual(ev2["data"]["session"], "s2")

        # Extra guard: no cross contamination in payloads
        self.assertNotIn('"m2"', json.dumps(ev1))
        self.assertNotIn('"m1"', json.dumps(ev2))
    
    def test_event_ordering_is_preserved(self):
        base = reverse("sse-subscribe")
        r = self.client.get(f"{base}?session_id=order")
        g = iter(r.streaming_content)
        first = next(g); _ = first.decode() if isinstance(first, (bytes, bytearray)) else first

        def push_all():
            sse.sse_send("order", "e", data={"n": 1})
            sse.sse_send("order", "e", data={"n": 2})
            sse.sse_send("order", "e", data={"n": 3})
        t = threading.Thread(target=push_all, daemon=True); t.start()

        def read_event(gen):
            chunk = next(gen)
            line = chunk.decode() if isinstance(chunk, (bytes, bytearray)) else chunk
            assert line.startswith("data: ")
            return json.loads(line[len("data: "):].strip())

        ev1, ev2, ev3 = read_event(g), read_event(g), read_event(g)
        t.join(timeout=1)

        assert ev1["data"]["n"] == 1
        assert ev2["data"]["n"] == 2
        assert ev3["data"]["n"] == 3