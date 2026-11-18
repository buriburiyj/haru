"""/eye: auth, the model request, size limit, memory without the photo, /eye/recent. The model is a fake."""
import base64
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_main import main, TestClient  # noqa: E402  (also sets the test environment)

import eye  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0" + b"fake-jpeg-bytes" * 10
IMAGE = base64.b64encode(JPEG).decode()
TOKEN = "eye-tests-token"


class EyeTest(unittest.TestCase):
    def setUp(self):
        os.environ["EYE_TOKEN"] = TOKEN
        self.client = TestClient(main.app)
        self.h = {"Authorization": "Bearer " + TOKEN}
        self.orig = (eye.call_model, eye.storage.read_file, eye.storage.commit_file, eye._entries)
        self.sent, self.saved, self.reply = [], [], "책상 위에 컵이 있어요.\nSCENE: 책상 위 컵 한 개"
        self.stored = None
        outer = self

        async def call_model(body, timeout):
            outer.sent.append((body, timeout))
            if isinstance(outer.reply, Exception):
                raise outer.reply
            return outer.reply

        async def read_file(path):
            return outer.stored

        async def commit_file(path, content, msg, queue_name):
            outer.stored = content
            outer.saved.append((path, content))
            return True

        eye.call_model, eye.storage.read_file, eye.storage.commit_file = call_model, read_file, commit_file
        eye._entries = None

    def tearDown(self):
        eye.call_model, eye.storage.read_file, eye.storage.commit_file, eye._entries = self.orig
        os.environ.pop("EYE_TOKEN", None)

    def post(self, **over):
        body = {"image": IMAGE, "question": "이게 뭐야?", "source": "mac", "deep": False, **over}
        return self.client.post("/eye", json=body, headers=self.h)

    def test_needs_the_eye_token_and_a_session_is_not_enough(self):
        self.assertEqual(self.client.post("/eye", json={}).status_code, 401)
        self.assertEqual(self.client.post("/eye", json={}, headers={"Authorization": "Bearer wrong"}).status_code, 401)
        self.assertEqual(self.client.get("/eye/recent").status_code, 401)
        os.environ.pop("EYE_TOKEN")  # unset token: nobody gets in, not even an empty Bearer
        self.assertEqual(self.client.post("/eye", json={}, headers={"Authorization": "Bearer "}).status_code, 401)
        self.assertEqual(self.sent, [])

    def test_answer_model_and_seconds_come_back(self):
        r = self.post()
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertEqual(d["answer"], "책상 위에 컵이 있어요.")  # the SCENE line is not part of the answer
        self.assertEqual(d["model"], "nvidia/nemotron-3.5-super-vl-120b-a12b")
        self.assertIsInstance(d["seconds"], (int, float))

    def test_fast_mode_turns_thinking_off_with_600_tokens(self):
        self.post(deep=False)
        body, timeout = self.sent[0]
        self.assertEqual(body["model"], eye.MODEL)
        self.assertEqual((body["max_tokens"], body["chat_template_kwargs"]), (600, {"enable_thinking": False}))
        parts = body["messages"][1]["content"]
        self.assertEqual(parts[0]["text"], "이게 뭐야?")
        self.assertTrue(parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))
        self.assertIn("한국어", body["messages"][0]["content"])

    def test_deep_mode_turns_thinking_on_with_2000_tokens(self):
        self.post(deep=True)
        body, _ = self.sent[0]
        self.assertEqual((body["max_tokens"], body["chat_template_kwargs"]), (2000, {"enable_thinking": True}))

    def test_think_blocks_are_dropped(self):
        self.reply = "<think>음...</think>사과예요.\nSCENE: 사과 한 개"
        self.assertEqual(self.post(deep=True).json()["answer"], "사과예요.")

    def test_image_over_1_5mb_is_413_and_the_model_is_not_called(self):
        big = base64.b64encode(b"\xff\xd8" + b"x" * 1_600_000).decode()
        self.assertEqual(self.post(image=big).status_code, 413)
        self.assertEqual(self.sent, [])
        ok = base64.b64encode(b"\xff\xd8" + b"x" * 1_400_000).decode()
        self.assertEqual(self.post(image=ok).status_code, 200)

    def test_bad_requests_are_400(self):
        for over in ({"image": ""}, {"image": "not base64!!"}, {"image": base64.b64encode(b"GIF89a").decode()},
                     {"question": " "}, {"source": "tv"}, {"deep": "yes"}):
            self.assertEqual(self.post(**over).status_code, 400, over)
        r = self.client.post("/eye", content=b"{oops", headers={**self.h, "Content-Type": "application/json"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.sent, [])

    def test_model_failures_are_reported_without_saving(self):
        self.reply = eye.EyeError(504, "model timeout")
        self.assertEqual(self.post().status_code, 504)
        self.reply = eye.EyeError(503, "model key is not set")
        self.assertEqual(self.post().status_code, 503)
        self.reply = "   "
        self.assertEqual(self.post().status_code, 502)
        self.assertEqual(self.saved, [])

    def test_memory_keeps_time_source_question_answer_scene_and_never_the_photo(self):
        self.post(source="phone", question="뭐가 보여?")
        path, content = self.saved[0]
        self.assertEqual(path, ".agent/eye/log.json")
        self.assertNotIn(IMAGE, content)
        self.assertNotIn("base64", content)
        entry = json.loads(content)["entries"][0]
        self.assertEqual(set(entry), {"time", "source", "question", "answer", "scene"})
        self.assertEqual((entry["source"], entry["question"], entry["scene"]), ("phone", "뭐가 보여?", "책상 위 컵 한 개"))

    def test_memory_survives_a_restart_and_recent_lists_newest_first_with_limit(self):
        for i in range(3):
            self.reply = f"답 {i}\nSCENE: 장면 {i}"
            self.post(question=f"질문 {i}")
        eye._entries = None  # a restart: the cache is gone, the store still has the log
        r = self.client.get("/eye/recent?limit=2", headers=self.h)
        self.assertEqual([e["question"] for e in r.json()["entries"]], ["질문 2", "질문 1"])
        self.assertEqual(len(self.client.get("/eye/recent", headers=self.h).json()["entries"]), 3)
        self.assertNotIn(IMAGE, r.text)

    def test_missing_scene_line_falls_back_to_the_first_line_of_the_answer(self):
        self.reply = "창문이 보여요. 밖은 맑아요."
        self.post()
        self.assertEqual(json.loads(self.saved[0][1])["entries"][0]["scene"], "창문이 보여요. 밖은 맑아요.")

    def test_log_is_capped(self):
        for i in range(eye.MAX_LOG + 5):
            asyncio_run(eye.remember({"time": i, "source": "mac", "question": "q", "answer": "a", "scene": "s"}))
        self.assertEqual(len(json.loads(self.stored)["entries"]), eye.MAX_LOG)


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)


if __name__ == "__main__":
    unittest.main()
