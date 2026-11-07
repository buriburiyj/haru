"""A Work task placeholder must survive later /chat saves and must not reach the model as an empty message."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_main import authed_client, main  # noqa: E402  (also sets the test environment)


class TaskPlaceholderSurvivesChatTest(unittest.TestCase):
    def test_clean_messages_keeps_valid_task_placeholders_only(self):
        out = main._clean_messages([
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "", "kind": "task", "taskId": "abcdef0123456789", "extra": 1},
            {"role": "assistant", "content": "", "kind": "task", "taskId": "../etc"},
            {"role": "user", "content": "x", "kind": "task", "taskId": "abcdef0123456789"},
        ])
        self.assertEqual(out[1], {"role": "assistant", "content": "", "kind": "task", "taskId": "abcdef0123456789"})
        self.assertNotIn("kind", out[2])  # bad id: plain empty message
        self.assertNotIn("kind", out[3])  # only assistant messages can be placeholders

    def test_chat_saves_placeholders_and_model_never_sees_an_empty_message(self):
        seen, saved = {}, {}

        async def route(messages, mode, effort=""):
            seen["prompt"] = messages
            yield "model", "m1"
            yield "delta", "ok"

        async def fake_save(chat_id, data, **kw):
            saved["messages"] = data["messages"]
            return True, {"id": chat_id, "title": "T"}

        orig = (main.router.route, main.storage.save_chat)
        main.router.route, main.storage.save_chat = route, fake_save
        try:
            body = {"chat_id": "w1", "messages": [
                {"role": "user", "content": "do work"},
                {"role": "assistant", "content": "", "kind": "task", "taskId": "abcdef0123456789"},
                {"role": "user", "content": "thanks"}]}
            self.assertEqual(authed_client().post("/chat", json=body).status_code, 200)
        finally:
            main.router.route, main.storage.save_chat = orig
        self.assertTrue(all(m["content"] for m in seen["prompt"] if isinstance(m["content"], str)))
        self.assertEqual(saved["messages"][1]["taskId"], "abcdef0123456789")
        self.assertEqual(saved["messages"][1]["kind"], "task")
        self.assertEqual(saved["messages"][-1]["role"], "assistant")


if __name__ == "__main__":
    unittest.main()
