"""API tests for auth gating, sessions and /chat. Run from server/: python -m unittest discover -s tests."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["SESSION_SECRET"] = "test-secret"
os.environ["CRED_FILE"] = str(Path(tempfile.mkdtemp()) / "creds.json")

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


def authed_client():
    c = TestClient(main.app, base_url="https://testserver")
    c.cookies.set(main.COOKIE, main._sign(int(time.time()) + 60))
    return c


class AuthTest(unittest.TestCase):
    def test_health_is_public(self):
        self.assertEqual(TestClient(main.app).get("/health").json(), {"status": "ok"})

    def test_chat_requires_session(self):
        self.assertEqual(TestClient(main.app).post("/chat", json={}).status_code, 401)

    def test_me_requires_session(self):
        self.assertEqual(TestClient(main.app).get("/auth/me").status_code, 401)
        self.assertEqual(authed_client().get("/auth/me").json(), {"ok": True})

    def test_bad_and_expired_tokens_rejected(self):
        self.assertFalse(main._valid("garbage"))
        self.assertFalse(main._valid(main._sign(int(time.time()) - 1)))
        exp, sig = main._sign(int(time.time()) + 60).split(".")
        self.assertFalse(main._valid(f"{exp}.{'0' * len(sig)}"))
        self.assertTrue(main._valid(main._sign(int(time.time()) + 60)))

    def test_login_unknown_credential_is_401(self):
        r = TestClient(main.app).post("/auth/login/verify", json={"id": "nope"})
        self.assertEqual(r.status_code, 401)

    def test_register_options_returns_challenge(self):
        r = TestClient(main.app).post("/auth/register/options")
        self.assertEqual(r.status_code, 200)
        self.assertIn("challenge", r.json())

    def test_register_verify_requires_setup_token(self):
        os.environ["SETUP_TOKEN"] = "s3"
        try:
            r = TestClient(main.app).post("/auth/register/verify", json={})
        finally:
            del os.environ["SETUP_TOKEN"]
        self.assertEqual(r.status_code, 401)


class CredStoreTest(unittest.TestCase):
    def test_save_commits_and_load_restores(self):
        import asyncio
        store = {}

        async def fake_commit(path, content, msg, queue_name):
            store[path] = content
            return True

        async def fake_read(path):
            return store.get(path)

        orig = (main.storage.commit_file, main.storage.read_file, main._cred_cache)
        main.storage.commit_file, main.storage.read_file = fake_commit, fake_read
        try:
            creds = [{"id": "a", "pk": "b", "count": 1}]
            asyncio.run(main._save_creds(creds))
            self.assertEqual(list(store), [main.CRED_REMOTE])
            self.assertNotIn("SESSION_SECRET", store[main.CRED_REMOTE])
            main._cred_cache = None
            Path(os.environ["CRED_FILE"]).unlink()  # simulate a wiped disk
            asyncio.run(main._load_remote_creds())
            self.assertEqual(main._creds(), creds)
        finally:
            main.storage.commit_file, main.storage.read_file, main._cred_cache = orig


class ChatTest(unittest.TestCase):
    def test_chat_streams_and_saves(self):
        saved = {}

        async def fake_route(messages, mode):
            yield "delta", "hel"
            yield "delta", "lo"

        async def fake_save(chat_id, data):
            saved.update(data)
            return True

        orig = (main.router.route, main.storage.save_chat)
        main.router.route, main.storage.save_chat = fake_route, fake_save
        try:
            r = authed_client().post(
                "/chat", json={"chat_id": "t1", "messages": [{"role": "user", "content": "hi"}]})
        finally:
            main.router.route, main.storage.save_chat = orig
        self.assertEqual(r.status_code, 200)
        self.assertIn("event: delta", r.text)
        self.assertIn("event: done", r.text)
        self.assertEqual(saved["messages"][-1], {"role": "assistant", "content": "hello"})


if __name__ == "__main__":
    unittest.main()
