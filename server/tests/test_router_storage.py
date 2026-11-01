"""Mock tests for router and storage. Run: python -m unittest discover -s tests (from server/)."""
import asyncio
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("GROQ_API_KEY", "x")
os.environ.setdefault("NVIDIA_API_KEY", "x")
os.environ.setdefault("GITHUB_TOKEN", "x")

REAL_CLIENT = httpx.AsyncClient

import router  # noqa: E402
import storage  # noqa: E402


def sse(*chunks):
    lines = [f"data: {json.dumps({'choices': [{'delta': {'content': c}}]})}\n\n" for c in chunks]
    return "".join(lines) + "data: [DONE]\n\n"


def patch_client(handler):
    """Make httpx.AsyncClient use a MockTransport."""
    class Mocked(REAL_CLIENT):
        def __init__(self, *a, **kw):
            kw["transport"] = httpx.MockTransport(handler)
            super().__init__(*a, **kw)

    httpx.AsyncClient = Mocked


async def collect(gen):
    return [x async for x in gen]


class RouterTest(unittest.TestCase):
    def tearDown(self):
        httpx.AsyncClient = REAL_CLIENT

    def test_easy_streams_from_groq(self):
        def h(req):
            return httpx.Response(200, text=sse("hi", "!"))
        patch_client(h)
        out = asyncio.run(collect(router.route([{"role": "user", "content": "hello"}], mode="easy")))
        self.assertEqual(out, [("delta", "hi"), ("delta", "!")])

    def test_hard_falls_back_to_nvidia(self):
        def h(req):
            if "nvidia" in req.url.host:
                return httpx.Response(200, text=sse("ok"))
            return httpx.Response(429)
        patch_client(h)
        orig = router.asyncio.sleep
        async def nosleep(_): pass
        router.asyncio.sleep = nosleep
        try:
            out = asyncio.run(collect(router.route([{"role": "user", "content": "code"}], mode="hard")))
        finally:
            router.asyncio.sleep = orig
        self.assertIn(("delta", "ok"), out)
        self.assertTrue(any(k == "notice" and "Switching" in t for k, t in out))

    def test_classify_defaults_hard_on_error(self):
        patch_client(lambda req: httpx.Response(500))
        async def run():
            async with httpx.AsyncClient() as c:
                return await router.classify(c, [{"role": "user", "content": "x"}])
        self.assertEqual(asyncio.run(run()), "hard")


class StorageTest(unittest.TestCase):
    def tearDown(self):
        httpx.AsyncClient = REAL_CLIENT

    def test_commit_success(self):
        puts = []
        def h(req):
            if req.method == "GET":
                return httpx.Response(404)
            puts.append(json.loads(req.content))
            return httpx.Response(201, json={})
        patch_client(h)
        self.assertTrue(asyncio.run(storage.save_chat("a/b", {"m": 1})))
        self.assertEqual(len(puts), 1)

    def test_failure_queues_then_flushes(self):
        with tempfile.TemporaryDirectory() as d:
            storage.QUEUE = Path(d)
            patch_client(lambda req: httpx.Response(500))
            self.assertFalse(asyncio.run(storage.save_chat("c1", {"m": 1})))
            self.assertEqual(len(list(Path(d).glob("*.json"))), 1)

            def ok(req):
                return httpx.Response(404 if req.method == "GET" else 201, json={})
            patch_client(ok)
            self.assertEqual(asyncio.run(storage.flush_queue()), 1)
            self.assertEqual(len(list(Path(d).glob("*.json"))), 0)


if __name__ == "__main__":
    unittest.main()
