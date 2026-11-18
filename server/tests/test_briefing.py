"""Morning briefing: due time (fake clock), once a day across restarts, content from fake materials, /brief."""
import asyncio
import json
import os
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_main import main  # noqa: E402  (also sets the test environment)

import briefing  # noqa: E402
import eye  # noqa: E402
import moment  # noqa: E402
import tg_chat  # noqa: E402

tasks = main.task_queue
KST = timezone(timedelta(hours=9))


def at(day, hour, minute=0):
    return datetime(2026, 11, day, hour, minute, tzinfo=KST)


def run(coro):
    return asyncio.run(coro)


class BriefingTest(unittest.TestCase):
    def setUp(self):
        os.environ["TELEGRAM_CHAT_ID"] = "42"
        os.environ.pop("BRIEF_HOUR", None)
        self.orig = (eye.llm, moment.search.search, eye.recent, briefing.storage.read_file, briefing.storage.commit_file, briefing._last_sent)
        self.sent, self.prompts, self.stored = [], [], None
        self.reply, self.weather, self.eyes = "좋은 아침이에요.\n서울은 맑고 12도예요.", [{"title": "서울 날씨", "url": "https://x.example", "snippet": "맑음 12도"}], []
        for d in (tasks.TASKS, tasks.EVENTS):
            d.clear()
        outer = self

        async def llm(messages, mode="easy"):
            outer.prompts.append(messages)
            if isinstance(outer.reply, Exception):
                raise outer.reply
            return outer.reply, "fake-fast"

        async def fake_search(query, limit=5):
            return outer.weather

        async def recent(limit=20):
            return outer.eyes[:limit]

        async def read_file(path):
            return outer.stored

        async def commit_file(path, content, msg, queue_name):
            outer.stored = content
            return True

        async def send(method, payload):
            outer.sent.append((method, payload))
            return True

        self.send = send
        eye.llm, moment.search.search, eye.recent, briefing.storage.read_file, briefing.storage.commit_file = llm, fake_search, recent, read_file, commit_file
        briefing._last_sent = None

    def tearDown(self):
        eye.llm, moment.search.search, eye.recent, briefing.storage.read_file, briefing.storage.commit_file, briefing._last_sent = self.orig
        for d in (tasks.TASKS, tasks.EVENTS):
            d.clear()
        os.environ.pop("TELEGRAM_CHAT_ID", None)
        os.environ.pop("BRIEF_HOUR", None)

    def finished(self, content, status, when, error=""):
        t = run(tasks.create(content, "auto", "c"))
        t.update(status=status, finished_at=when.timestamp())
        if error:
            tasks.add_event(t["id"], "failed", {"error": error})
        return t

    def test_not_before_eight_kst_and_sent_once_after(self):
        self.assertFalse(run(briefing.tick(at(18, 7, 59), self.send)))
        self.assertEqual(self.sent, [])
        self.assertTrue(run(briefing.tick(at(18, 8, 0), self.send)))
        self.assertFalse(run(briefing.tick(at(18, 8, 1), self.send)))
        self.assertFalse(run(briefing.tick(at(18, 23, 0), self.send)))
        self.assertEqual(len(self.sent), 1)
        method, payload = self.sent[0]
        self.assertEqual((method, payload["chat_id"]), ("sendMessage", "42"))

    def test_next_day_sends_again(self):
        run(briefing.tick(at(18, 9), self.send))
        run(briefing.tick(at(19, 7), self.send))
        self.assertEqual(len(self.sent), 1)
        run(briefing.tick(at(19, 8, 30), self.send))
        self.assertEqual(len(self.sent), 2)

    def test_a_restart_does_not_send_twice(self):
        run(briefing.tick(at(18, 8, 5), self.send))
        self.assertEqual(json.loads(self.stored), {"last": "2026-11-18"})
        briefing._last_sent = None  # the server restarted: memory gone, the store still has the date
        self.assertFalse(run(briefing.tick(at(18, 8, 6), self.send)))
        self.assertEqual(len(self.sent), 1)

    def test_an_unreadable_store_sends_nothing(self):
        async def broken(path):
            raise RuntimeError("store down")
        briefing.storage.read_file = broken
        self.assertFalse(run(briefing.tick(at(18, 9), self.send)))
        self.assertEqual(self.sent, [])

    def test_a_failed_send_is_tried_again_next_minute_and_not_marked(self):
        async def failing(method, payload):
            return False
        self.assertFalse(run(briefing.tick(at(18, 8, 0), failing)))
        self.assertIsNone(self.stored)
        self.assertTrue(run(briefing.tick(at(18, 8, 1), self.send)))

    def test_brief_hour_env_changes_the_time_and_no_chat_id_sends_nothing(self):
        os.environ["BRIEF_HOUR"] = "6"
        self.assertTrue(run(briefing.tick(at(18, 6, 0), self.send)))
        os.environ["BRIEF_HOUR"] = "oops"
        self.assertEqual(briefing.brief_hour(), 8)
        os.environ.pop("TELEGRAM_CHAT_ID")
        briefing._last_sent = ""
        self.assertFalse(run(briefing.tick(at(19, 12), self.send)))

    def test_material_is_weather_yesterday_to_today_tasks_and_recent_eye_records(self):
        now = at(18, 8, 0)
        self.finished("README 요약", "done", at(18, 7))
        self.finished("어제 끝난 일", "done", at(17, 15))
        self.finished("그저께 일", "done", at(16, 20))  # older than yesterday: left out
        self.finished("빌드 확인", "failed", at(17, 22), error="일꾼 응답 없음")
        self.eyes = [{"scene": "책상 위 열쇠", "question": "이거 뭐야?"}, {"scene": "창밖 맑음", "question": "날씨 보여?"}, {"scene": "셋째", "question": "q"}]
        text = run(briefing.compose(now))
        body = self.prompts[0][1]["content"]
        self.assertIn("맑음 12도", body)
        self.assertIn("끝난 작업: README 요약", body)
        self.assertIn("끝난 작업: 어제 끝난 일", body)
        self.assertIn("실패한 작업: 빌드 확인 (일꾼 응답 없음)", body)
        self.assertNotIn("그저께", body)
        self.assertIn("책상 위 열쇠", body)
        self.assertIn("창밖 맑음", body)
        self.assertNotIn("셋째", body)  # one or two eye records
        self.assertNotIn("https://", body)
        self.assertIn("2~3문장", self.prompts[0][0]["content"])
        self.assertEqual(text, "좋은 아침이에요.\n서울은 맑고 12도예요.")

    def test_empty_parts_are_left_out_and_with_nothing_at_all_no_model_is_asked(self):
        self.weather = []
        self.finished("끝난 일", "done", at(18, 7))
        run(briefing.compose(at(18, 8)))
        body = self.prompts[0][1]["content"]
        self.assertIn("[어제~오늘 Work 작업]", body)
        self.assertNotIn("서울 날씨", body)
        self.assertNotIn("하루 눈", body)
        tasks.TASKS.clear()
        self.prompts.clear()
        text = run(briefing.compose(at(18, 8)))
        self.assertEqual(self.prompts, [])
        self.assertIn("좋은 아침", text)

    def test_output_is_plain_at_most_five_lines(self):
        self.reply = "# 아침이에요\n- **맑아요** [링크](https://x.example/a)\n둘째 https://y.example\n3\n4\n5\n6\n7"
        text = run(briefing.compose(at(18, 8)))
        lines = text.splitlines()
        self.assertEqual(len(lines), 5)
        for bad in ("#", "*", "[", "http", "- "):
            self.assertNotIn(bad, text)
        self.assertIn("맑아요 링크", text)

    def test_model_failure_falls_back_to_a_plain_message_from_the_material(self):
        self.reply = RuntimeError("down")
        self.finished("README 요약", "done", at(18, 7))
        text = run(briefing.compose(at(18, 8)))
        self.assertIn("좋은 아침", text)
        self.assertIn("맑음 12도", text)
        self.assertIn("README 요약", text)

    def test_brief_in_telegram_sends_now_without_touching_the_daily_date(self):
        body = {"update_id": 900, "message": {"chat": {"id": 42}, "text": "/brief"}}
        tg_chat.SEEN.clear()
        self.assertTrue(run(tg_chat.handle(body, send=self.send)))
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.sent[0][1]["text"], "좋은 아침이에요.\n서울은 맑고 12도예요.")
        self.assertIsNone(self.stored)  # the daily record is untouched
        self.assertTrue(run(briefing.tick(at(18, 9), self.send)))  # the real one still goes out
        other = {"update_id": 901, "message": {"chat": {"id": 7}, "text": "/brief"}}
        self.assertFalse(run(tg_chat.handle(other, send=self.send)))  # only the owner's chat


if __name__ == "__main__":
    unittest.main()
