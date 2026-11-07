"""API tests for auth gating, sessions and /chat. Run from server/: python -m unittest discover -s tests."""
import base64
import hashlib
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "worker"))
os.environ["SESSION_SECRET"] = "test-secret"
os.environ["HARU_DISABLE_LLM"] = "1"  # no Groq calls from tests
os.environ.pop("SETUP_TOKEN", None)  # a real token in the shell must not change test results
os.environ["CRED_FILE"] = str(Path(tempfile.mkdtemp()) / "creds.json")
os.environ.setdefault("WORKER_TOKEN", "worker-tests-only")

import cbor2  # noqa: E402
from cryptography.hazmat.primitives import hashes  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
import haru_worker  # noqa: E402


async def _offline_state(chat_id):
    return False, ""


main._chat_state = _offline_state  # no GitHub lookup in tests

main.memory._mem = {}  # no network: memory index is treated as loaded and empty


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def authed_client():
    c = TestClient(main.app, base_url="https://testserver")
    c.headers["Authorization"] = f"Bearer {main._sign(int(time.time()) + 60)}"
    return c


class AuthTest(unittest.TestCase):
    def test_health_is_public(self):
        self.assertEqual(TestClient(main.app).get("/health").json(), {"status": "ok"})

    def test_task_worker_auth_and_task_controls(self):
        import tasks
        os.environ["WORKER_TOKEN"] = "worker-test-token"
        try:
            c = authed_client()
            r = c.post("/tasks", json={"content": "work", "mode": "auto", "conversation_id": "c1"})
            self.assertEqual(r.status_code, 200, r.text)
            task_id = r.json()["id"]
            worker = TestClient(main.app, base_url="https://testserver")
            self.assertEqual(worker.post("/worker/claim", json={"worker_id": "w"}).status_code, 401)
            worker.headers["X-Worker-Token"] = "worker-test-token"
            claimed = worker.post("/worker/claim", json={"worker_id": "w"}).json()["task"]
            self.assertEqual(claimed["id"], task_id)
            self.assertTrue(worker.post("/worker/heartbeat", json={"task_id": task_id, "worker_id": "w", "checkpoint": "abc"}).json()["ok"])
            self.assertEqual(worker.post("/worker/done", json={"task_id": task_id, "result": "ok"}).status_code, 200)
            self.assertEqual(c.get(f"/tasks/{task_id}/events").status_code, 200)
        finally:
            os.environ.pop("WORKER_TOKEN", None)


    def test_chat_requires_session(self):
        self.assertEqual(TestClient(main.app).post("/chat", json={}).status_code, 401)

    def test_me_requires_session(self):
        self.assertEqual(TestClient(main.app).get("/auth/me").status_code, 401)
        self.assertEqual(authed_client().get("/auth/me").json(), {"ok": True})

    def test_cors_on_401_and_setup_token_preflight(self):
        o = "https://buriburiyj.github.io"
        c = TestClient(main.app)
        r = c.get("/auth/me", headers={"Origin": o})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.headers.get("access-control-allow-origin"), o)
        p = c.options("/auth/register/options", headers={
            "Origin": o, "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-setup-token"})
        self.assertEqual(p.status_code, 200)

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


class WorkerPolicyTest(unittest.TestCase):
    def test_command_policy_blocks_danger_and_classifies_auto_actions(self):
        self.assertTrue(haru_worker.safe_command("ls -la && head -n 1 README.md"))
        self.assertEqual(haru_worker.command_class("ls -la && head -n 1 README.md"), "read")
        self.assertFalse(haru_worker.safe_command("cat ~/.env"))
        self.assertFalse(haru_worker.safe_command("rm -rf build"))
        self.assertFalse(haru_worker.safe_command("git push origin main"))
        self.assertEqual(haru_worker.command_class("python3 script.py"), "unknown")

    def test_worker_plan_uses_server_router_and_returns_json_action(self):
        import asyncio
        os.environ["WORKER_TOKEN"] = "router-test-token"
        task = asyncio.run(main.task_queue.create("list files and summarize README", "auto", "c1"))
        client = TestClient(main.app)
        client.headers["X-Worker-Token"] = "router-test-token"
        original = main.router.route
        calls = []

        async def fake_route(messages, mode, effort=""):
            calls.append((messages, mode))
            yield "model", "test-model"
            yield "delta", '{"command":"ls -la && head -n 1 README.md","summary":"README first line summary"}'

        main.router.route = fake_route
        try:
            result = client.post("/worker/plan", json={"task_id": task["id"], "entries": ["README.md"]})
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(result.json()["command"], "ls -la && head -n 1 README.md")
            self.assertEqual(calls[0][1], "auto")
            self.assertIn("README.md", calls[0][0][0]["content"])
        finally:
            main.router.route = original
            os.environ.pop("WORKER_TOKEN", None)


class PasskeyFlowTest(unittest.TestCase):
    """Full register -> login flow with a software authenticator, no cookies involved."""

    def setUp(self):
        import asyncio
        self.orig = (main.storage.commit_file, main._cred_cache)

        async def fake_commit(*a, **k):
            return True

        main.storage.commit_file = fake_commit
        main._cred_cache = []
        self.client = TestClient(main.app)
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.cred_id = os.urandom(16)

    def tearDown(self):
        main.storage.commit_file, main._cred_cache = self.orig

    def _client_data(self, typ, challenge):
        return json.dumps({"type": typ, "challenge": challenge, "origin": main.ORIGIN, "crossOrigin": False}).encode()

    def _register(self):
        o = self.client.post("/auth/register/options").json()
        nums = self.key.public_key().public_numbers()
        cose = cbor2.dumps({1: 2, 3: -7, -1: 1, -2: nums.x.to_bytes(32, "big"), -3: nums.y.to_bytes(32, "big")})
        auth = (hashlib.sha256(main.RP_ID.encode()).digest() + bytes([0x45]) + (0).to_bytes(4, "big")
                + bytes(16) + len(self.cred_id).to_bytes(2, "big") + self.cred_id + cose)
        body = {"id": b64u(self.cred_id), "rawId": b64u(self.cred_id), "type": "public-key", "response": {
            "clientDataJSON": b64u(self._client_data("webauthn.create", o["challenge"])),
            "attestationObject": b64u(cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth}))}}
        return self.client.post("/auth/register/verify", json=body, headers={"X-Challenge-Id": o["challenge_id"]})

    def _login(self, count=1):
        o = self.client.post("/auth/login/options").json()
        auth = hashlib.sha256(main.RP_ID.encode()).digest() + bytes([0x05]) + count.to_bytes(4, "big")
        cd = self._client_data("webauthn.get", o["challenge"])
        sig = self.key.sign(auth + hashlib.sha256(cd).digest(), ec.ECDSA(hashes.SHA256()))
        body = {"id": b64u(self.cred_id), "rawId": b64u(self.cred_id), "type": "public-key", "response": {
            "clientDataJSON": b64u(cd), "authenticatorData": b64u(auth), "signature": b64u(sig),
            "userHandle": None}}
        return self.client.post("/auth/login/verify", json=body, headers={"X-Challenge-Id": o["challenge_id"]})

    def test_register_then_login_with_bearer_token(self):
        r = self._register()
        self.assertEqual(r.status_code, 200, r.text)
        self.assertNotIn("set-cookie", r.headers)
        self.assertEqual(self.client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['token']}"}).status_code, 200)
        r = self._login()
        self.assertEqual(r.status_code, 200, r.text)
        tok = r.json()["token"]
        self.assertEqual(self.client.get("/auth/me", headers={"Authorization": f"Bearer {tok}"}).status_code, 200)
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_second_registration_needs_session(self):
        self.assertEqual(self._register().status_code, 200)
        self.assertEqual(self.client.post("/auth/register/options").status_code, 401)

    def test_challenge_id_is_bound_to_purpose_and_signature(self):
        ch = os.urandom(32)
        cid = main._make_challenge_id("reg", ch)
        self.assertEqual(main._open_challenge_id(cid, "reg"), ch)
        self.assertIsNone(main._open_challenge_id(cid, "auth"))
        self.assertIsNone(main._open_challenge_id(cid[:-2] + "00", "reg"))
        self.assertIsNone(main._open_challenge_id("", "reg"))

    def test_verify_without_challenge_id_fails(self):
        self.assertEqual(self.client.post("/auth/register/verify", json={}).status_code, 400)


class UsageApiTest(unittest.TestCase):
    def test_usage_needs_session_and_has_no_billing_fields(self):
        self.assertEqual(TestClient(main.app).get("/usage").status_code, 401)

        async def fake_usage():
            return {"minutes_used": 3, "minutes_limit": 1500, "runs": 2, "resets_at": 1}

        orig = main.codex.usage
        main.codex.usage = fake_usage
        try:
            d = authed_client().get("/usage").json()
        finally:
            main.codex.usage = orig
        self.assertEqual(set(d), {"as_of", "codex", "groq", "nvidia"})
        self.assertEqual(d["codex"]["minutes_limit"], 1500)
        self.assertEqual(set(d["groq"]), {"calls_today", "rate_limited_today", "resets_at"})
        text = json.dumps(d).lower()
        for banned in ("price", "cost", "bill", "pay", "usd", "$"):
            self.assertNotIn(banned, text)

    def test_usage_survives_github_failure(self):
        async def boom():
            raise RuntimeError("github down")

        orig = main.codex.usage
        main.codex.usage = boom
        try:
            d = authed_client().get("/usage").json()
        finally:
            main.codex.usage = orig
        self.assertIsNone(d["codex"])
        self.assertIn("groq", d)


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
            main.CRED_FILE.unlink(missing_ok=True)  # simulate a wiped disk
            asyncio.run(main._load_remote_creds())
            self.assertEqual(main._creds(), creds)
        finally:
            main.storage.commit_file, main.storage.read_file, main._cred_cache = orig


class ReadOnlyDiskTest(unittest.TestCase):
    def test_save_creds_survives_unwritable_disk(self):
        import asyncio

        async def fake_commit(*a, **k):
            return True

        orig = (main.storage.commit_file, main.CRED_FILE, main._cred_cache)
        main.storage.commit_file = fake_commit
        main.CRED_FILE = Path("/proc/nope/credentials.json")  # cannot be created
        try:
            asyncio.run(main._save_creds([{"id": "a", "pk": "b", "count": 0}]))
            self.assertEqual(main._creds()[0]["id"], "a")
        finally:
            main.storage.commit_file, main.CRED_FILE, main._cred_cache = orig

    def test_queue_write_failure_does_not_raise(self):
        import storage
        orig = storage.QUEUE
        storage.QUEUE = Path("/proc/nope/queue")
        try:
            storage._enqueue("x", "p", "c")
        finally:
            storage.QUEUE = orig


class ChatTest(unittest.TestCase):
    def _post(self, body, fake_route=None):
        saved = {}

        async def default_route(messages, mode, effort=""):
            yield "model", "m1"
            yield "delta", "hel"
            yield "delta", "lo"

        async def fake_save(chat_id, data, **kw):
            saved.update(data)
            return True, {"id": chat_id, "title": "T"}

        orig = (main.router.route, main.storage.save_chat)
        main.router.route, main.storage.save_chat = fake_route or default_route, fake_save
        try:
            r = authed_client().post("/chat", json=body)
        finally:
            main.router.route, main.storage.save_chat = orig
        return r, saved

    def test_chat_streams_saves_and_reports_model_only_in_done(self):
        r, saved = self._post({"chat_id": "t1", "messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(r.status_code, 200)
        self.assertIn("event: delta", r.text)
        self.assertNotIn("Switching", r.text)
        done = json.loads(r.text.split("event: done\ndata: ")[1].split("\n")[0])
        self.assertEqual(done, {"chat_id": "t1", "saved": True, "model": "m1", "title": "T", "temporary": False,
                                "project_id": None, "artifacts": [], "sources": []})
        self.assertEqual(saved["messages"][-1], {"role": "assistant", "content": "hello", "model": "m1"})

    def test_search_adds_context_and_sources(self):
        seen = {}

        async def spy(messages, mode, effort=""):
            seen["m"] = messages
            yield "model", "m1"
            yield "delta", "It is sunny [1]."

        async def fake_search(q):
            seen["q"] = q
            return [{"title": "Weather", "url": "https://w.example/a", "snippet": "sunny"}]

        orig = main.search.search
        main.search.search = fake_search
        try:
            r, saved = self._post({"chat_id": "s1", "messages": [{"role": "user", "content": "오늘 서울 날씨"}]}, spy)
        finally:
            main.search.search = orig
        self.assertEqual(seen["q"], "오늘 서울 날씨")
        self.assertEqual(seen["m"][0]["role"], "system")
        self.assertIn("https://w.example/a", seen["m"][0]["content"])
        self.assertIn("출처", r.text)
        self.assertIn("https://w.example/a", saved["messages"][-1]["content"])
        done = json.loads(r.text.split("event: done\ndata: ")[1].split("\n")[0])
        self.assertEqual(done["sources"], [{"title": "Weather", "url": "https://w.example/a"}])

    def test_search_off_and_failure_still_answer(self):
        async def boom(q):
            return []

        orig = main.search.search
        main.search.search = boom
        try:
            r, saved = self._post({"chat_id": "s2", "web": "on", "messages": [{"role": "user", "content": "hi"}]})
        finally:
            main.search.search = orig
        self.assertIn("event: delta", r.text)
        self.assertNotIn("출처", r.text)

    def test_temporary_chat_is_not_saved(self):
        r, saved = self._post({"chat_id": "tmp", "temporary": True, "messages": [{"role": "user", "content": "secret"}]})
        self.assertEqual(saved, {})
        done = json.loads(r.text.split("event: done\ndata: ")[1].split("\n")[0])
        self.assertEqual((done["saved"], done["temporary"]), (False, True))

    def test_effort_is_validated_and_forwarded(self):
        seen = []

        async def spy(messages, mode, effort=""):
            seen.append(effort)
            yield "delta", "x"

        for given in ("high", "extreme", None):
            body = {"messages": [{"role": "user", "content": "hi"}]}
            if given is not None:
                body["effort"] = given
            self._post(body, spy)
        self.assertEqual(seen, ["high", "", ""])

    def test_no_answer_is_not_saved(self):
        async def none_route(messages, mode, effort=""):
            yield "notice", "All models unavailable"

        r, saved = self._post({"chat_id": "t2", "messages": [{"role": "user", "content": "hi"}]}, none_route)
        self.assertEqual(saved, {})
        self.assertIn('"saved": false', r.text)

    def test_messages_are_sanitized(self):
        seen = {}

        async def spy(messages, mode, effort=""):
            seen["m"], seen["mode"] = messages, mode
            yield "delta", "x"

        self._post({"messages": [{"role": "user", "content": "a", "extra": 1}, {"role": "evil", "content": "b"},
                                 {"role": "user", "content": 5}], "mode": "bogus"}, spy)
        self.assertEqual(seen["m"], [{"role": "user", "content": "a"}])
        self.assertEqual(seen["mode"], "auto")

    def test_models_and_chats_endpoints(self):
        c = authed_client()
        self.assertEqual(c.get("/models").json()["default"], "auto")

        async def fake_list(q, limit, project_id=""):
            return [{"id": "x"}]

        async def fake_get(cid):
            return None

        orig = (main.storage.list_chats, main.storage.get_chat)
        main.storage.list_chats, main.storage.get_chat = fake_list, fake_get
        try:
            self.assertEqual(c.get("/chats").json(), {"chats": [{"id": "x"}]})
            self.assertEqual(c.get("/chats/nope").status_code, 404)
        finally:
            main.storage.list_chats, main.storage.get_chat = orig
        self.assertEqual(TestClient(main.app).get("/chats").status_code, 401)
        self.assertEqual(TestClient(main.app).delete("/chats/x").status_code, 401)


if __name__ == "__main__":
    unittest.main()
