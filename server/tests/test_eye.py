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


class EyeTalkTest(unittest.TestCase):
    """No photo: the fast model decides (photo / past / search / plain), sessions keep the last 6 turns."""

    def setUp(self):
        os.environ["EYE_TOKEN"] = TOKEN
        self.client = TestClient(main.app)
        self.h = {"Authorization": "Bearer " + TOKEN}
        self.orig = (eye.llm, eye.search.search, eye.storage.read_file, eye.storage.commit_file, eye._entries, eye.call_model)
        self.calls, self.searches, self.plan, self.answers = [], [], '{"past":false,"need_photo":false,"search":""}', []
        self.results = []
        self.stored = None
        outer = self

        async def llm(messages, mode="easy"):
            outer.calls.append(messages)
            if messages[0]["content"].startswith(eye.PLAN_SYSTEM[:10]):
                return outer.plan, "fake-fast"
            return (outer.answers.pop(0) if outer.answers else "네, 알겠어요."), "fake-fast"

        async def fake_search(query, limit=5):
            outer.searches.append(query)
            return outer.results

        async def read_file(path):
            return outer.stored

        async def commit_file(path, content, msg, queue_name):
            outer.stored = content
            return True

        async def call_model(body, timeout):
            outer.calls.append(body["messages"])
            return "열쇠예요.\nSCENE: 책상 위 열쇠"

        eye.llm, eye.search.search, eye.storage.read_file, eye.storage.commit_file, eye.call_model = llm, fake_search, read_file, commit_file, call_model
        eye._entries = None
        eye._sessions.clear()

    def tearDown(self):
        eye.llm, eye.search.search, eye.storage.read_file, eye.storage.commit_file, eye._entries, eye.call_model = self.orig
        eye._sessions.clear()
        os.environ.pop("EYE_TOKEN", None)

    def post(self, question, **over):
        return self.client.post("/eye", json={"question": question, **over}, headers=self.h)

    def test_image_is_optional_and_the_response_has_all_four_fields(self):
        self.answers = ["서울은 대한민국의 수도예요."]
        r = self.post("서울이 어느 나라 수도야?")
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertEqual(set(d), {"answer", "need_photo", "model", "seconds"})
        self.assertEqual((d["answer"], d["need_photo"], d["model"]), ("서울은 대한민국의 수도예요.", False, "fake-fast"))

    def test_a_question_that_needs_the_photo_gets_only_need_photo_true(self):
        self.plan = '{"past":false,"need_photo":true,"search":""}'
        d = self.post("이거 뭐야?", session="s1").json()
        self.assertEqual((d["need_photo"], d["answer"]), (True, ""))
        self.assertEqual(len(self.calls), 1)  # only the planner ran, no answer was written
        self.assertEqual(self.searches, [])
        self.assertEqual(eye.history_of("s1"), [])  # the question is asked again with the photo

    def test_unreadable_plan_falls_back_to_keywords(self):
        self.plan = "음... 모르겠어요"
        self.assertTrue(self.post("저거 읽어 줘").json()["need_photo"])
        self.answers = ["네."]
        self.assertFalse(self.post("안녕").json()["need_photo"])

    def test_search_runs_only_when_the_planner_gives_a_query_and_links_stay_out(self):
        self.plan = '{"past":false,"need_photo":false,"search":"서울 날씨"}'
        self.results = [{"title": "서울 날씨", "url": "https://example.com/w", "snippet": "맑고 기온은 12도"}]
        self.answers = ["**오늘 서울은 맑고 12도예요.** [1] https://example.com/w 우산은 필요 없어요."]
        d = self.post("오늘 서울 날씨 어때?").json()
        self.assertEqual(self.searches, ["서울 날씨"])
        self.assertIn("맑고 기온은 12도", self.calls[-1][0]["content"])
        self.assertNotIn("example.com", self.calls[-1][0]["content"])  # links are not given to the model
        self.assertEqual(d["answer"], "오늘 서울은 맑고 12도예요. 우산은 필요 없어요.")
        self.plan = '{"past":false,"need_photo":false,"search":""}'
        self.post("고마워")
        self.assertEqual(self.searches, ["서울 날씨"])  # plain plan: no second search

    def test_answers_are_plain_text_for_reading_aloud(self):
        self.answers = ["# 제목\n- 첫째: **빠르게**\n- 둘째 [링크](https://x.example/a)\n`코드`"]
        a = self.post("설명해 줘").json()["answer"]
        for bad in ("#", "*", "`", "[", "](", "http", "\n"):
            self.assertNotIn(bad, a)
        self.assertIn("빠르게", a)
        self.assertIn("링크", a)
        self.assertIn("2~3문장", self.calls[-1][0]["content"])

    def test_what_i_saw_earlier_is_answered_from_the_eye_log(self):
        self.post("이거 뭐야?", source="phone", image=IMAGE)  # one photo turn is logged
        self.plan = '{"past":true,"need_photo":false,"search":""}'
        self.answers = ["아까는 책상 위 열쇠를 봤어요."]
        d = self.post("아까 본 게 뭐였지?").json()
        self.assertEqual((d["answer"], d["need_photo"]), ("아까는 책상 위 열쇠를 봤어요.", False))
        system = self.calls[-1][0]["content"]
        self.assertIn("책상 위 열쇠", system)
        self.assertIn("이거 뭐야?", system)
        self.assertEqual(self.searches, [])

    def test_a_session_keeps_the_last_six_turns_and_uses_them(self):
        for i in range(8):
            self.answers = [f"답 {i}"]
            self.post(f"질문 {i}", session="abc")
        self.assertEqual([q for q, a in eye.history_of("abc")], [f"질문 {i}" for i in range(2, 8)])
        self.answers = ["이어서 답해요."]
        self.post("그럼 그다음은?", session="abc")
        sent = self.calls[-1]
        self.assertEqual([m["content"] for m in sent[1:-1:2]], [f"질문 {i}" for i in range(2, 8)])
        self.assertEqual(sent[-1]["content"], "그럼 그다음은?")
        self.assertEqual(eye.history_of("other"), [])  # sessions do not mix

    def test_a_photo_turn_joins_the_session_for_follow_ups(self):
        self.post("이거 뭐야?", image=IMAGE, session="p1")
        self.assertEqual(eye.history_of("p1"), [("이거 뭐야?", "열쇠예요.")])
        self.post("그게 어디 있었지?", image=IMAGE, session="p1")
        self.assertEqual(self.calls[-1][1]["content"], "이거 뭐야?")  # the earlier turn went in as text

    def test_bad_session_is_400_and_no_model_is_503(self):
        self.assertEqual(self.post("안녕", session="x" * 65).status_code, 400)
        self.assertEqual(self.post("안녕", session=5).status_code, 400)
        self.answers = [" "]
        self.assertEqual(self.post("안녕").status_code, 503)

    def test_old_sessions_are_dropped_beyond_the_cap(self):
        for i in range(eye.MAX_SESSIONS + 3):
            eye.remember_turn(f"s{i}", "q", "a")
        self.assertEqual(len(eye._sessions), eye.MAX_SESSIONS)
        self.assertNotIn("s0", eye._sessions)


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)


if __name__ == "__main__":
    unittest.main()
