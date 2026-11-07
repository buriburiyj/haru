import asyncio
import os
import sys
import tempfile
import types
import unittest
from collections import deque
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import notify  # noqa: E402


class FakeSend:
    def __init__(self):
        self.calls = []

    async def __call__(self, method, payload):
        self.calls.append((method, payload))
        return True


def make():
    fake = FakeSend()
    n = notify.Notifier(send=fake, now=lambda: datetime(2026, 11, 7, 12, tzinfo=notify.KST),
                        queue_file=os.path.join(tempfile.mkdtemp(), "q.json"), chat_id="42")
    return n, fake


def fake_queue(task):
    q = types.SimpleNamespace(TASKS={"t1": task}, events=[])

    def add_event(task_id, kind, data):
        q.events.append((task_id, kind, data))

    def publish(task_id, kind, data):  # real publish may call add_event internally
        q.add_event(task_id, kind, data)

    q.add_event, q.publish = add_event, publish
    return q


async def settle():
    await asyncio.sleep(0)
    await asyncio.gather(*list(notify._background))


def press(data, chat=42):
    return {"callback_query": {"id": "c1", "data": data, "message": {"chat": {"id": chat}}}}


class HookTest(unittest.TestCase):
    def setUp(self):
        notify._skipped.clear()
        notify._waiting.clear()

    def test_done_once_with_skipped_count(self):
        n, fake = make()
        q = fake_queue({"content": "README 정리", "permissions": deque()})
        notify.install(q, n)

        async def run():
            q.add_event("t1", "skipped", {})
            q.publish("t1", "done", {"result": "ok"})
            await settle()
        asyncio.run(run())
        self.assertEqual(len(fake.calls), 1)
        text = fake.calls[0][1]["text"]
        self.assertIn("README 정리", text)
        self.assertIn("건너뛴 단계 1개", text)

    def test_failed_includes_error(self):
        n, fake = make()
        q = fake_queue({"content": "빌드", "permissions": deque()})
        notify.install(q, n)

        async def run():
            q.add_event("t1", "failed", {"error": "npm 오류"})
            await settle()
        asyncio.run(run())
        self.assertIn("npm 오류", fake.calls[0][1]["text"])

    def test_button_accepted_for_pending_request(self):
        n, fake = make()
        task = {"content": "정리", "permissions": deque(), "pending_permission": {"id": "a1"}}
        q = fake_queue(task)
        notify.install(q, n)

        async def run():
            q.publish("t1", "permission_required", {"id": "a1", "title": "build 폴더 지우기", "kind": "delete"})
            await settle()
        asyncio.run(run())
        row = fake.calls[0][1]["reply_markup"]["inline_keyboard"][0]
        self.assertEqual([b["text"] for b in row], ["허락", "거절"])
        self.assertIn("build 폴더 지우기", fake.calls[0][1]["text"])
        self.assertTrue(asyncio.run(notify.handle_update(press(row[0]["callback_data"]), q, n)))
        self.assertEqual(list(task["permissions"]), ["allow"])
        self.assertEqual(q.events[-1][1], "permission")
        self.assertEqual(fake.calls[-1][0], "answerCallbackQuery")

    def test_stale_button_rejected(self):
        n, fake = make()
        task = {"content": "정리", "permissions": deque(), "pending_permission": {"id": "a1"}}
        q = fake_queue(task)
        notify.install(q, n)

        async def run():
            q.publish("t1", "permission_required", {"id": "a1", "label": "x"})
            await settle()
        asyncio.run(run())
        data = fake.calls[0][1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        q.add_event("t1", "permission", {"decision": "allow"})  # decided in the app
        self.assertFalse(asyncio.run(notify.handle_update(press(data), q, n)))
        self.assertEqual(list(task["permissions"]), [])

    def test_wrong_chat_ignored(self):
        n, fake = make()
        task = {"content": "x", "permissions": deque(), "pending_permission": "a1"}
        q = fake_queue(task)
        asyncio.run(n.ask_permission("t1", "a1", "x"))
        data = fake.calls[0][1]["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        self.assertFalse(asyncio.run(notify.handle_update(press(data, chat=99), q, n)))
        self.assertEqual(list(task["permissions"]), [])

    def test_no_event_loop_is_safe(self):
        n, fake = make()
        q = fake_queue({"content": "x", "permissions": deque()})
        notify.install(q, n)
        q.add_event("t1", "done", {})
        self.assertEqual(fake.calls, [])


if __name__ == "__main__":
    unittest.main()
