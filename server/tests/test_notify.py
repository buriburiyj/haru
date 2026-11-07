import asyncio
import os
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import notify  # noqa: E402


def at(hour):
    return lambda: datetime(2026, 11, 7, hour, 0, tzinfo=notify.KST)


class FakeSend:
    def __init__(self, ok=True):
        self.calls, self.ok = [], ok

    async def __call__(self, method, payload):
        self.calls.append((method, payload))
        return self.ok


def make(hour, ok=True, path=None):
    fake = FakeSend(ok)
    path = path or os.path.join(tempfile.mkdtemp(), "q.json")
    return notify.Notifier(send=fake, now=at(hour), queue_file=path, chat_id="42"), fake, path


def update(chat, data):
    return {"callback_query": {"id": "c1", "data": data, "message": {"chat": {"id": chat}}}}


class NotifyTest(unittest.TestCase):
    def test_quiet_hours_boundaries(self):
        self.assertTrue(notify.is_quiet(at(23)()))
        self.assertTrue(notify.is_quiet(at(7)()))
        self.assertFalse(notify.is_quiet(at(8)()))
        self.assertFalse(notify.is_quiet(at(22)()))

    def test_daytime_sends_now(self):
        n, fake, _ = make(12)
        self.assertTrue(asyncio.run(n.notify("done", "README 정리")))
        self.assertEqual(fake.calls[0][0], "sendMessage")
        self.assertIn("README 정리", fake.calls[0][1]["text"])
        self.assertEqual(fake.calls[0][1]["chat_id"], "42")

    def test_night_batches_then_morning_digest(self):
        n, fake, path = make(23)
        asyncio.run(n.notify("failed", "A 작업"))
        self.assertEqual(fake.calls, [])
        n2, fake2, _ = make(9, path=path)  # survives restart via queue file
        asyncio.run(n2.notify("done", "B 작업"))
        self.assertIn("밤사이 알림 1개", fake2.calls[0][1]["text"])
        self.assertIn("A 작업", fake2.calls[0][1]["text"])
        self.assertIn("B 작업", fake2.calls[1][1]["text"])
        self.assertEqual(n2._pending, [])

    def test_failed_digest_keeps_pending(self):
        n, _, path = make(2)
        asyncio.run(n.notify("done", "A"))
        n2, _, _ = make(9, ok=False, path=path)
        self.assertFalse(asyncio.run(n2.flush()))
        self.assertEqual(len(n2._pending), 1)

    def test_digest_is_capped(self):
        n, fake, _ = make(1)
        for i in range(100):
            asyncio.run(n.notify("done", "작업" * 60 + str(i)))
        self.assertEqual(len(n._pending), notify.MAX_PENDING)
        n._now = at(9)
        asyncio.run(n.flush())
        self.assertLess(len(fake.calls[0][1]["text"]), 4096)

    def test_permission_buttons_and_single_use(self):
        n, fake, _ = make(12)
        asyncio.run(n.ask_permission("t1", "r1", "파일 지우기", kind="delete"))
        row = fake.calls[0][1]["reply_markup"]["inline_keyboard"][0]
        self.assertEqual([b["text"] for b in row], ["허락", "거절"])
        self.assertLessEqual(len(row[0]["callback_data"].encode()), 64)
        self.assertIsNone(n.resolve_callback(update(99, row[0]["callback_data"])))
        self.assertEqual(n.resolve_callback(update(42, row[0]["callback_data"])), ("t1", "r1", "allow", "c1"))
        self.assertIsNone(n.resolve_callback(update(42, row[1]["callback_data"])))

    def test_safe_kind_has_always_and_silent_at_night(self):
        n, fake, _ = make(0)
        asyncio.run(n.ask_permission("t2", "r2", "테스트 실행"))
        payload = fake.calls[0][1]
        self.assertEqual([b["text"] for b in payload["reply_markup"]["inline_keyboard"][0]], ["허락", "항상 허락", "거절"])
        self.assertTrue(payload["disable_notification"])

    def test_unknown_or_missing_chat(self):
        n, fake, _ = make(12)
        self.assertIsNone(n.resolve_callback(update(42, "p:nope")))
        off = notify.Notifier(send=fake, now=at(12), queue_file=os.path.join(tempfile.mkdtemp(), "q.json"), chat_id="")
        self.assertFalse(asyncio.run(off.notify("done", "x")))
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()
