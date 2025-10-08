import unittest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

User = get_user_model()

class ChatFlowTests(APITestCase):
    def setUp(self):
        # dipanggil tiap test → DB test otomatis pakai in-memory sesuai settings Django
        self.user = User.objects.create_user(username="geordie", password="pw")
        # auth-kan client
        self.client.force_authenticate(user=self.user)

    def test_create_session_returns_201_and_session_id(self):
        """User bisa buat chat session dan menerima UUID."""
        url = reverse("chat:create_session")
        resp = self.client.post(url, {"title": "Uji Klinis A"}, format="json")
        self.assertEqual(resp.status_code, 201, msg=resp.content)
        data = resp.json()
        self.assertIn("id", data)
        self.assertIsInstance(data["id"], str)
        self.assertGreaterEqual(len(data["id"]), 32)

    def test_add_messages_and_fetch_history_in_order(self):
        """Pesan tersimpan dan urut lama→baru saat diambil kembali."""
        # create session
        sid = self.client.post(reverse("chat:create_session"), {"title": ""}, format="json").json()["id"]

        # add messages
        r1 = self.client.post(reverse("chat:post_message", args=[sid]),
                              {"role": "user", "content": "Halo"}, format="json")
        self.assertEqual(r1.status_code, 201)

        r2 = self.client.post(reverse("chat:post_message", args=[sid]),
                              {"role": "assistant", "content": "Hai, ada yang bisa dibantu?"}, format="json")
        self.assertEqual(r2.status_code, 201)

        # fetch history
        rh = self.client.get(reverse("chat:get_messages", args=[sid]))
        self.assertEqual(rh.status_code, 200)
        msgs = rh.json()
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant"])
        self.assertEqual(msgs[0]["content"], "Halo")

    def test_ask_returns_answer_and_persists_assistant_message(self):
        """
        /ask mengembalikan jawaban (200) dan menyimpan pesan assistant ke history.
        Jika integrasi LLM/DB belum siap, test ini memang akan FAIL (RED).
        """
        sid = self.client.post(reverse("chat:create_session"), {"title": "Demo"}, format="json").json()["id"]

        rq = self.client.post(reverse("chat:ask", args=[sid]),
                              {"question": "Berapa total data pasien tersimpan?"}, format="json")
        self.assertEqual(rq.status_code, 200, msg=rq.content)
        answer = rq.json().get("answer", "")
        self.assertIsInstance(answer, str)
        self.assertGreater(len(answer), 0)

        # history harus berisi user & assistant
        rh = self.client.get(reverse("chat:get_messages", args=[sid]))
        msgs = rh.json()
        roles = [m["role"] for m in msgs]
        self.assertGreaterEqual(roles.count("user"), 1)
        self.assertGreaterEqual(roles.count("assistant"), 1)


if __name__ == "__main__":
    unittest.main()
