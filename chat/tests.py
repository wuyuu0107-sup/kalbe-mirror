# chat/tests.py
import unittest
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

User = get_user_model()

class ChatFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="geordie", password="pw")
        self.client.force_authenticate(user=self.user)

    def test_create_session_returns_201_and_session_id(self):
        resp = self.client.post(reverse("chat:create_session"), {"title": "Uji Klinis A"}, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertIn("id", resp.json())

    def test_add_messages_and_fetch_history_in_order(self):
        sid = self.client.post(reverse("chat:create_session"), {"title": ""}, format="json").json()["id"]
        self.assertEqual(
            self.client.post(reverse("chat:post_message", args=[sid]),
                             {"role":"user","content":"Halo"}, format="json").status_code, 201
        )
        self.assertEqual(
            self.client.post(reverse("chat:post_message", args=[sid]),
                             {"role":"assistant","content":"Hai"}, format="json").status_code, 201
        )
        msgs = self.client.get(reverse("chat:get_messages", args=[sid])).json()
        self.assertEqual([m["role"] for m in msgs], ["user","assistant"])

    @patch("chat.service.DB")  # mock DB layer supaya gak query DB beneran
    @patch("chat.service.get_intent_json")  # mock panggilan ke Gemini
    def test_ask_returns_answer_and_persists_assistant_message(self, mock_llm, mock_db_cls):
        # 1) siapkan mock LLM -> balikin intent JSON valid
        mock_llm.return_value = '{"intent":"TOTAL_PATIENTS","args":{}}'

        # 2) siapkan mock DB.fetch_one -> hitungannya 123
        mock_db = mock_db_cls.return_value
        mock_db.fetch_one.return_value = (123,)

        sid = self.client.post(reverse("chat:create_session"), {"title": "Demo"}, format="json").json()["id"]

        rq = self.client.post(reverse("chat:ask", args=[sid]),
                              {"question": "Berapa total data pasien tersimpan?"}, format="json")

        self.assertEqual(rq.status_code, 200, msg=rq.content)
        self.assertIn("123", rq.json()["answer"])

        msgs = self.client.get(reverse("chat:get_messages", args=[sid])).json()
        roles = [m["role"] for m in msgs]
        self.assertGreaterEqual(roles.count("user"), 1)
        self.assertGreaterEqual(roles.count("assistant"), 1)
