import asyncio, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tg_chat


def msg(text, chat=42, uid=1):
    return {"update_id": uid, "message": {"chat": {"id": chat}, "text": text}}


async def fake_route(messages, mode):
    assert mode == "easy"
    yield "model", "m"
    yield "delta", "답"
    yield "delta", "변"


async def fake_find(q):
    return [{"title": "T", "url": "https://x.kr", "snippet": "S"}]


class T(unittest.TestCase):
    def setUp(self):
        os.environ["TELEGRAM_CHAT_ID"] = "42"
        tg_chat.SEEN.clear(); tg_chat.HISTORY.clear()
        self.sent = []

    async def send(self, method, payload):
        self.sent.append((method, payload)); return True

    def test_other_chat_ignored(self):
        self.assertIsNone(tg_chat.accept(msg("hi", chat=7)))

    def test_retry_ignored(self):
        self.assertEqual(tg_chat.accept(msg("hi", uid=5)), "hi")
        self.assertIsNone(tg_chat.accept(msg("hi", uid=5)))

    def test_answer_uses_search(self):
        seen = {}
        async def route(m, mode):
            seen["m"] = m
            async for x in fake_route(m, mode): yield x
        r = asyncio.run(tg_chat.answer("날씨", route=route, find=fake_find, need=lambda m, w: True))
        self.assertEqual(r, "답변")
        self.assertIn("https://x.kr", str(seen["m"]))
        self.assertEqual(len(tg_chat.HISTORY), 2)

    def test_handle_replies(self):
        ok = asyncio.run(tg_chat.handle(msg("안녕"), send=self.send, route=fake_route, find=fake_find, need=lambda m, w: False))
        self.assertTrue(ok)
        self.assertEqual([m for m, _ in self.sent], ["sendChatAction", "sendMessage"])
        self.assertEqual(self.sent[-1][1], {"chat_id": "42", "text": "답변", "disable_web_page_preview": True})

    def test_model_error_message(self):
        async def bad(m, mode):
            raise RuntimeError("x"); yield
        asyncio.run(tg_chat.handle(msg("안녕"), send=self.send, route=bad, find=fake_find, need=lambda m, w: False))
        self.assertIn("오류", self.sent[-1][1]["text"])

    def test_other_chat_no_send(self):
        self.assertFalse(asyncio.run(tg_chat.handle(msg("hi", chat=7), send=self.send)))
        self.assertEqual(self.sent, [])


if __name__ == "__main__":
    unittest.main()
