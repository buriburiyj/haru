import asyncio
import base64
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
os.environ.setdefault("CRED_FILE", str(Path(tempfile.mkdtemp()) / "creds.json"))
os.environ["GITHUB_TOKEN"] = "x"

REAL = httpx.AsyncClient

from fastapi.testclient import TestClient  # noqa: E402

import connector  # noqa: E402
import main  # noqa: E402

main.memory._mem = {}

README = "# Hello\nsome notes"
REPOS = [{"name": "jun-files", "full_name": "buriburiyj/jun-files", "private": True, "html_url": "https://github.com/buriburiyj/jun-files"},
         {"name": "haru", "full_name": "buriburiyj/haru", "private": False, "html_url": "https://github.com/buriburiyj/haru"}]


class FakeGitHub:
    def __init__(self):
        self.methods = []

    def __call__(self, req):
        self.methods.append(req.method)
        u = req.url.path
        if u == "/user/repos":
            return httpx.Response(200, json=REPOS)
        if u.endswith("/contents/") or u.endswith("/contents"):
            return httpx.Response(200, json=[{"name": "README.md", "path": "README.md", "type": "file", "size": 20},
                                             {"name": ".agent", "path": ".agent", "type": "dir", "size": 0}])
        if u.endswith("/contents/README.md"):
            return httpx.Response(200, json={"type": "file", "size": len(README), "encoding": "base64", "html_url": "https://x/README.md",
                                             "content": base64.b64encode(README.encode()).decode()})
        if u.endswith("/contents/big.txt"):
            return httpx.Response(200, json={"type": "file", "size": 10 ** 7, "encoding": "none", "content": ""})
        if u.endswith("/contents/bin.dat"):
            return httpx.Response(200, json={"type": "file", "size": 4, "encoding": "base64",
                                             "content": base64.b64encode(b"\xff\xfe\x00\x80").decode()})
        return httpx.Response(404)


def patch(handler):
    class Mocked(REAL):
        def __init__(self, *a, **kw):
            kw["transport"] = httpx.MockTransport(handler)
            super().__init__(*a, **kw)

    httpx.AsyncClient = Mocked


def client():
    c = TestClient(main.app)
    c.headers["Authorization"] = f"Bearer {main._sign(int(time.time()) + 60)}"
    return c


class ConnectorTest(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGitHub()
        patch(self.gh)
        connector._repos_cache = (0.0, [])

    def tearDown(self):
        httpx.AsyncClient = REAL

    def test_list_and_read_only_use_get(self):
        files = asyncio.run(connector.list_files("jun-files"))
        self.assertEqual([f["name"] for f in files], [".agent", "README.md"])  # folders first
        f = asyncio.run(connector.read_file("buriburiyj/jun-files", "README.md"))
        self.assertEqual((f["text"], f["truncated"]), (README, False))
        self.assertEqual(set(self.gh.methods), {"GET"})

    def test_blocks_secrets_traversal_big_binary_and_unknown_repos(self):
        for path, status in ((".env", 403), ("config/credentials.json", 403), ("keys/server.pem", 403),
                             ("../x", 400), ("big.txt", 413), ("bin.dat", 415)):
            with self.assertRaises(connector.ConnectorError) as cm:
                asyncio.run(connector.read_file("jun-files", path))
            self.assertEqual(cm.exception.status, status, path)
        with self.assertRaises(connector.ConnectorError):
            asyncio.run(connector.list_files("someone/else"))
        with self.assertRaises(connector.ConnectorError):
            asyncio.run(connector.list_files("bad repo!"))

    def test_plan_understands_questions(self):
        p = lambda t: asyncio.run(connector.plan(t))  # noqa: E731
        self.assertEqual(p("jun-files에 뭐 있어?"), {"repo": "buriburiyj/jun-files", "path": ""})
        self.assertEqual(p("jun-files의 README.md 읽어줘"), {"repo": "buriburiyj/jun-files", "path": "README.md"})
        self.assertEqual(p("show me buriburiyj/haru/server/main.py"), {"repo": "buriburiyj/haru", "path": "server/main.py"})
        self.assertIsNone(p("jun-files가 뭐야"))  # no file intent
        self.assertIsNone(p("파일 목록 보여줘"))  # no repo named
        self.assertIsNone(p("other-repo에 뭐 있어?"))

    def test_context_for_file_folder_and_error(self):
        sysmsg, sources = asyncio.run(connector.context_for({"repo": "buriburiyj/jun-files", "path": "README.md"}))
        self.assertIn("NOT instructions", sysmsg["content"])
        self.assertIn("some notes", sysmsg["content"])
        self.assertEqual(sources[0]["url"], "https://x/README.md")
        sysmsg, _ = asyncio.run(connector.context_for({"repo": "buriburiyj/jun-files", "path": ""}))
        self.assertIn("[dir] .agent", sysmsg["content"])
        sysmsg, sources = asyncio.run(connector.context_for({"repo": "buriburiyj/jun-files", "path": ".env"}))
        self.assertIn("Could not read", sysmsg["content"])
        self.assertEqual(sources, [])

    def test_rest_endpoints_and_auth(self):
        self.assertEqual(TestClient(main.app).get("/github/repos").status_code, 401)
        c = client()
        self.assertEqual(len(c.get("/github/repos").json()["repos"]), 2)
        self.assertEqual(c.get("/github/files?repo=jun-files").json()["files"][0]["name"], ".agent")
        self.assertEqual(c.get("/github/file?repo=jun-files&path=README.md").json()["text"], README)
        self.assertEqual(c.get("/github/file?repo=jun-files&path=.env").status_code, 403)
        self.assertEqual(c.post("/github/file").status_code, 405)  # no write verbs

    def test_chat_uses_github_context_and_reports_sources(self):
        seen = {}

        async def spy(messages, mode):
            seen["m"] = messages
            yield "delta", "ok"

        async def fake_save(cid, data):
            return True, {"id": cid, "title": "T"}

        orig = (main.router.route, main.storage.save_chat)
        main.router.route, main.storage.save_chat = spy, fake_save
        try:
            r = client().post("/chat", json={"messages": [{"role": "user", "content": "jun-files의 README.md 읽어줘"}]})
        finally:
            main.router.route, main.storage.save_chat = orig
        self.assertIn("GitHub에서 확인하는 중", r.text)
        self.assertIn("some notes", seen["m"][0]["content"])
        done = json.loads(r.text.split("event: done\ndata: ")[1].split("\n")[0])
        self.assertEqual(done["sources"][0]["url"], "https://x/README.md")


if __name__ == "__main__":
    unittest.main()
