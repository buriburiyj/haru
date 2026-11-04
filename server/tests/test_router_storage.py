"""Mock tests for router and storage. Run: python -m unittest discover -s tests (from server/)."""
import asyncio
import base64
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
    def setUp(self):
        self._sleep = router.asyncio.sleep

        async def nosleep(_):
            pass

        router.asyncio.sleep = nosleep

    def tearDown(self):
        httpx.AsyncClient = REAL_CLIENT
        router.asyncio.sleep = self._sleep

    def run_route(self, mode):
        return asyncio.run(collect(router.route([{"role": "user", "content": "hello"}], mode=mode)))

    def test_easy_streams_from_groq_and_reports_model(self):
        patch_client(lambda req: httpx.Response(200, text=sse("hi", "!")))
        out = self.run_route("easy")
        self.assertEqual(out, [("model", router.GROQ_MODEL), ("delta", "hi"), ("delta", "!")])

    def test_no_internal_switching_text(self):
        def h(req):
            return httpx.Response(200, text=sse("ok")) if "nvidia" in req.url.host else httpx.Response(429)
        patch_client(h)
        out = self.run_route("hard")
        self.assertIn(("model", router.NVIDIA_MODELS[0]), out)
        self.assertFalse(any("Switching" in str(v) for _, v in out))

    def test_easy_falls_back_to_nvidia_when_groq_fails(self):
        def h(req):
            return httpx.Response(200, text=sse("ok")) if "nvidia" in req.url.host else httpx.Response(404)
        patch_client(h)
        self.assertIn(("delta", "ok"), self.run_route("easy"))

    def test_direct_model_has_no_fallback(self):
        patch_client(lambda req: httpx.Response(503))
        out = self.run_route(router.NVIDIA_MODELS[1])
        self.assertEqual(out, [("notice", "All models unavailable")])

    def test_models_list_is_auto_groq_codex_nvidia_only(self):
        ms = router.models()
        self.assertEqual(ms[0], {"id": "auto", "label": "자동", "provider": "auto"})
        self.assertEqual([m["provider"] for m in ms],
                         ["auto", "groq", "codex", "codex", "codex", "nvidia", "nvidia", "nvidia"])
        self.assertEqual([m["id"] for m in ms if m["provider"] == "codex"],
                         ["gpt-6-luna", "gpt-5.6-terra", "gpt-5.6-luna"])
        names = " ".join(m["id"] for m in ms)
        for gone in ("kimi", "glm", "llama-3.1-8b"):
            self.assertNotIn(gone, names)
        self.assertEqual(len({m["id"] for m in ms}), len(ms))

    def test_auto_is_not_a_direct_model(self):
        patch_client(lambda req: httpx.Response(200, text=sse("x")))
        out = self.run_route("auto")  # goes through classification, not a model called "auto"
        self.assertTrue(any(k == "delta" for k, _ in out))

    def test_classify_defaults_hard_on_error(self):
        patch_client(lambda req: httpx.Response(500))

        async def run():
            async with httpx.AsyncClient() as c:
                return await router.classify(c, [{"role": "user", "content": "x"}])
        self.assertEqual(asyncio.run(run()), "hard")


class FakeGitHub:
    """Minimal GitHub: Git Data API (ref/commit/tree/commit/ref) and Contents GET."""

    def __init__(self):
        self.files, self.commits, self.pending, self.fail_index_read, self.down = {}, [], None, False, False

    def __call__(self, req):
        u, m = req.url.path, req.method
        if self.down:
            return httpx.Response(500)
        if "/git/ref/heads/" in u:
            return httpx.Response(200, json={"object": {"sha": "h1"}})
        if "/git/commits/" in u and m == "GET":
            return httpx.Response(200, json={"tree": {"sha": "t1"}})
        if u.endswith("/git/trees"):
            self.pending = json.loads(req.content)["tree"]
            return httpx.Response(201, json={"sha": "t2"})
        if u.endswith("/git/commits") and m == "POST":
            return httpx.Response(201, json={"sha": "h2"})
        if "/git/refs/heads/" in u:
            self.commits.append(self.pending)
            for e in self.pending:
                if e.get("sha", 1) is None:
                    self.files.pop(e["path"], None)
                else:
                    self.files[e["path"]] = e["content"]
            return httpx.Response(200, json={})
        if "/contents/" in u and m == "GET":
            path = u.split("/contents/", 1)[1]
            if self.fail_index_read and path.endswith("index.json"):
                return httpx.Response(500)
            if path in self.files:
                return httpx.Response(200, json={"content": base64.b64encode(self.files[path].encode()).decode()})
            return httpx.Response(404)
        return httpx.Response(404)

    def index(self):
        return json.loads(self.files[storage.INDEX_PATH])["chats"]


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGitHub()
        patch_client(self.gh)
        storage._index = None
        self.tmp = tempfile.TemporaryDirectory()
        storage.QUEUE = Path(self.tmp.name)

    def tearDown(self):
        httpx.AsyncClient = REAL_CLIENT
        storage._index = None
        self.tmp.cleanup()

    def msgs(self, text="hello there", answer="hi!"):
        return [{"role": "user", "content": text}, {"role": "assistant", "content": answer}]

    def test_one_commit_per_answer_includes_index(self):
        ok, meta = asyncio.run(storage.save_chat("a/b", {"messages": self.msgs()}))
        self.assertTrue(ok)
        self.assertEqual(len(self.gh.commits), 1)
        self.assertEqual({e["path"] for e in self.gh.commits[0]}, {".agent/chats/ab.json", storage.INDEX_PATH})
        self.assertEqual(self.gh.index()[0]["id"], "ab")
        self.assertEqual(meta["title"], "hello there")

    def test_second_answer_keeps_title_and_adds_one_commit(self):
        asyncio.run(storage.save_chat("c1", {"messages": self.msgs()}))
        asyncio.run(storage.rename_chat("c1", "My title"))
        asyncio.run(storage.save_chat("c1", {"messages": self.msgs() + self.msgs("more", "ok")}))
        self.assertEqual(self.gh.index()[0]["title"], "My title")
        self.assertEqual(len(self.gh.commits), 3)

    def test_list_search_get_delete(self):
        asyncio.run(storage.save_chat("c1", {"messages": self.msgs("python sort", "use sorted")}))
        asyncio.run(storage.save_chat("c2", {"messages": self.msgs("recipe", "boil water")}))
        self.assertEqual([m["id"] for m in asyncio.run(storage.list_chats())], ["c2", "c1"])
        self.assertEqual([m["id"] for m in asyncio.run(storage.list_chats("SORTED"))], ["c1"])
        self.assertEqual(asyncio.run(storage.get_chat("c1"))["messages"][1]["content"], "use sorted")
        self.assertTrue(asyncio.run(storage.delete_chat("c1")))
        self.assertNotIn(".agent/chats/c1.json", self.gh.files)
        self.assertEqual([m["id"] for m in self.gh.index()], ["c2"])
        self.assertFalse(asyncio.run(storage.delete_chat("nope")))

    def test_failure_queues_then_flush_commits_with_index(self):
        self.gh.down = True
        ok, _ = asyncio.run(storage.save_chat("c1", {"messages": self.msgs()}))
        self.assertFalse(ok)
        self.assertEqual(len(list(Path(self.tmp.name).glob("*.json"))), 1)
        self.gh.down = False
        self.assertEqual(asyncio.run(storage.flush_queue()), 1)
        self.assertIn(".agent/chats/c1.json", self.gh.files)
        self.assertEqual([m["id"] for m in self.gh.index()], ["c1"])

    def test_unreadable_index_never_overwrites_existing_index(self):
        asyncio.run(storage.save_chat("old", {"messages": self.msgs("keep me", "ok")}))
        storage._index = None
        self.gh.fail_index_read = True
        ok, _ = asyncio.run(storage.save_chat("new", {"messages": self.msgs("fresh", "ok")}))
        self.assertFalse(ok)
        self.assertEqual(len(self.gh.commits), 1)  # nothing written while the index is unreadable
        self.gh.fail_index_read = False
        self.assertEqual(asyncio.run(storage.flush_queue()), 1)
        self.assertEqual({m["id"] for m in self.gh.index()}, {"old", "new"})

    def test_queue_write_failure_does_not_raise(self):
        orig = storage.QUEUE
        storage.QUEUE = Path("/proc/nope/queue")
        try:
            storage._enqueue("x", "p", "c")
        finally:
            storage.QUEUE = orig


if __name__ == "__main__":
    unittest.main()
