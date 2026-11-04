import asyncio
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["SESSION_SECRET"] = "test-secret"
os.environ["HARU_DISABLE_LLM"] = "1"  # no Groq calls from tests
os.environ.setdefault("CRED_FILE", str(Path(tempfile.mkdtemp()) / "creds.json"))
os.environ["GITHUB_TOKEN"] = "x"

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


async def _offline_state(chat_id):
    return False, ""


main._chat_state = _offline_state  # no GitHub lookup in tests
import memory  # noqa: E402
from test_router_storage import FakeGitHub, REAL_CLIENT, patch_client  # noqa: E402


def client():
    c = TestClient(main.app)
    c.headers["Authorization"] = f"Bearer {main._sign(int(time.time()) + 60)}"
    return c


class MemoryApiTest(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGitHub()
        patch_client(self.gh)
        memory._mem = None

    def tearDown(self):
        httpx.AsyncClient = REAL_CLIENT
        memory._mem = {}

    def index(self):
        return json.loads(self.gh.files[memory.INDEX_PATH])["memories"]

    def test_crud_one_commit_each_with_index(self):
        c = client()
        e = c.post("/memory", json={"topic": "Coffee", "content": "Likes oat latte"}).json()
        self.assertTrue(memory.valid_id(e["id"]))
        self.assertEqual(len(self.gh.commits), 1)
        self.assertEqual({x["path"] for x in self.gh.commits[0]}, {f".agent/memory/{e['id']}.json", memory.INDEX_PATH})
        self.assertEqual(c.get("/memory").json()["memories"][0]["topic"], "Coffee")
        u = c.put(f"/memory/{e['id']}", json={"content": "Likes black coffee"}).json()
        self.assertEqual((u["topic"], u["content"]), ("Coffee", "Likes black coffee"))
        self.assertEqual(self.index()[0]["content"], "Likes black coffee")
        self.assertEqual(c.get(f"/memory/{e['id']}").json()["id"], e["id"])
        self.assertEqual(c.delete(f"/memory/{e['id']}").json(), {"ok": True})
        self.assertNotIn(f".agent/memory/{e['id']}.json", self.gh.files)
        self.assertEqual(self.index(), [])
        self.assertEqual(c.delete(f"/memory/{e['id']}").status_code, 404)

    def test_validation_and_auth(self):
        c = client()
        self.assertEqual(c.post("/memory", json={"topic": "", "content": "x"}).status_code, 400)
        self.assertEqual(c.post("/memory", json={"topic": "t", "content": "x" * 2001}).status_code, 400)
        self.assertEqual(c.get("/memory/..%2Fx").status_code, 404)
        self.assertEqual(c.put("/memory/nope-123", json={"content": "x"}).status_code, 404)
        for method in ("get", "delete"):
            self.assertEqual(getattr(TestClient(main.app), method)("/memory").status_code, 401)

    def test_failed_commit_rolls_back(self):
        c = client()
        self.gh.down = True
        self.assertEqual(c.post("/memory", json={"topic": "t", "content": "x"}).status_code, 502)
        self.gh.down = False
        self.assertEqual(c.get("/memory").json(), {"memories": []})

    def test_extract_request(self):
        self.assertEqual(memory.extract_request("기억해줘: 나는 채식해"), "나는 채식해")
        self.assertEqual(memory.extract_request("기억해 내 생일은 3월"), "내 생일은 3월")
        self.assertEqual(memory.extract_request("Remember that I use Vim"), "I use Vim")
        self.assertIsNone(memory.extract_request("나는 어제 기억해냈어"))
        self.assertIsNone(memory.extract_request("hello"))


class MemoryInChatTest(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGitHub()
        patch_client(self.gh)
        memory._mem = None
        self.seen = {}

        async def spy(messages, mode, effort=""):
            self.seen["m"] = messages
            yield "delta", "ok"

        async def fake_save(cid, data, **kw):
            self.seen["saved"] = True
            return True, {"id": cid, "title": "T"}

        self.orig = (main.router.route, main.storage.save_chat)
        main.router.route, main.storage.save_chat = spy, fake_save

    def tearDown(self):
        main.router.route, main.storage.save_chat = self.orig
        httpx.AsyncClient = REAL_CLIENT
        memory._mem = {}

    def post(self, **extra):
        return client().post("/chat", json={"chat_id": "c", "messages": [{"role": "user", "content": extra.pop("text", "hi")}], **extra})

    def test_memories_are_injected_in_normal_chats(self):
        asyncio.run(memory.create("Diet", "Vegetarian"))
        self.post()
        self.assertEqual(self.seen["m"][0]["role"], "system")
        self.assertIn("Diet: Vegetarian", self.seen["m"][0]["content"])

    def test_temporary_chat_neither_reads_nor_writes_memory(self):
        asyncio.run(memory.create("Diet", "Vegetarian"))
        commits = len(self.gh.commits)
        self.post(temporary=True, text="기억해줘: 비밀 계획")
        self.assertEqual(self.seen["m"], [{"role": "user", "content": "기억해줘: 비밀 계획"}])  # nothing injected
        self.assertEqual(len(self.gh.commits), commits)  # nothing written
        self.assertNotIn("saved", self.seen)

    def test_remember_command_saves_and_notifies(self):
        r = self.post(text="기억해줘: 나는 매운 음식을 좋아해")
        self.assertIn("기억했어요", r.text)
        self.assertEqual(asyncio.run(memory.list_all())[0]["content"], "나는 매운 음식을 좋아해")


if __name__ == "__main__":
    unittest.main()
