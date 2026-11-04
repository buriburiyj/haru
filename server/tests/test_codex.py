"""Codex-through-Actions tests with a fake GitHub (no network)."""
import asyncio
import base64
import json
import os
import sys
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("GROQ_API_KEY", "x")
os.environ.setdefault("NVIDIA_API_KEY", "x")
os.environ["GITHUB_TOKEN"] = "x"

REAL_CLIENT = httpx.AsyncClient

import codex  # noqa: E402
import router  # noqa: E402
import storage  # noqa: E402


class FakeActions:
    def __init__(self):
        self.files, self.dispatches, self.polls = {}, [], 0
        self.out_after, self.dispatch_status, self.run_state = 2, 204, "queued"
        self.out = {"ok": True, "model": "gpt-6-luna", "text": "answer " * 100}

    def __call__(self, req):
        u, m = req.url.path, req.method
        if u.endswith("/dispatches"):
            self.dispatches.append(json.loads(req.content))
            return httpx.Response(self.dispatch_status)
        if u.endswith("/runs"):
            if self.run_state == "none":
                return httpx.Response(200, json={"workflow_runs": []})
            run = {"created_at": "2999-01-01T00:00:00Z", "status": "completed" if self.run_state == "failed" else "queued",
                   "conclusion": "failure" if self.run_state == "failed" else None}
            return httpx.Response(200, json={"workflow_runs": [run]})
        if "/contents/" in u:
            path = u.split("/contents/", 1)[1]
            if m == "PUT":
                self.files[path] = base64.b64decode(json.loads(req.content)["content"]).decode()
                return httpx.Response(201, json={})
            if path.endswith(".out.json"):
                self.polls += 1
                if self.polls >= self.out_after:
                    return httpx.Response(200, json={"content": base64.b64encode(json.dumps(self.out).encode()).decode()})
                return httpx.Response(404)
            if path in self.files:
                return httpx.Response(200, json={"sha": "s", "content": base64.b64encode(self.files[path].encode()).decode()})
            return httpx.Response(404)
        return httpx.Response(404)


def patch(handler):
    class Mocked(REAL_CLIENT):
        def __init__(self, *a, **kw):
            kw["transport"] = httpx.MockTransport(handler)
            super().__init__(*a, **kw)

    httpx.AsyncClient = Mocked


async def collect(gen):
    return [x async for x in gen]


class CodexTest(unittest.TestCase):
    def setUp(self):
        self.gh = FakeActions()
        patch(self.gh)
        self.cleaned = []

        async def fake_cleanup(job):
            self.cleaned.append(job)

        async def nosleep(_):
            pass

        self.orig = (codex._cleanup, codex.asyncio.sleep, codex._disabled_until, codex._usage,
                     codex.TOTAL_TIMEOUT, codex.MONTHLY_LIMIT_MIN)
        codex._cleanup, codex.asyncio.sleep = fake_cleanup, nosleep
        codex._disabled_until, codex._usage = 0.0, None
        self.msgs = [{"role": "user", "content": "explain quicksort"}]

    def tearDown(self):
        httpx.AsyncClient = REAL_CLIENT
        (codex._cleanup, codex.asyncio.sleep, codex._disabled_until, codex._usage,
         codex.TOTAL_TIMEOUT, codex.MONTHLY_LIMIT_MIN) = self.orig

    def run_codex(self, models=None):
        async def go():
            return await collect(codex.run(self.msgs, models or router.CODEX_MODELS))
        return asyncio.run(go())

    def test_success_streams_text_and_records_usage(self):
        out = self.run_codex()
        self.assertEqual(out[0][0], "notice")
        self.assertIn(("model", "gpt-6-luna"), out)
        self.assertEqual("".join(v for k, v in out if k == "delta"), self.gh.out["text"])
        self.assertTrue(all(len(v) <= codex.CHUNK for k, v in out if k == "delta"))
        job_file = next(p for p in self.gh.files if p.startswith(".agent/jobs/"))
        self.assertEqual(json.loads(self.gh.files[job_file])["models"], router.CODEX_MODELS)
        self.assertEqual(self.gh.dispatches[0]["inputs"]["job"], job_file.split("/")[-1][:-5])
        self.assertEqual(json.loads(self.gh.files[codex.USAGE_PATH])["runs"], 1)
        self.assertEqual(len(self.cleaned), 1)

    def test_all_models_failed(self):
        self.gh.out = {"ok": False, "tried": router.CODEX_MODELS}
        with self.assertRaises(codex.CodexUnavailable):
            self.run_codex()

    def test_dispatch_forbidden_trips_breaker(self):
        self.gh.dispatch_status = 403
        with self.assertRaises(codex.CodexUnavailable):
            self.run_codex()
        n = len(self.gh.dispatches)
        with self.assertRaises(codex.CodexUnavailable):
            self.run_codex()
        self.assertEqual(len(self.gh.dispatches), n)  # second call never reached GitHub

    def test_monthly_budget_blocks_dispatch(self):
        codex._usage = {"month": codex._month(), "minutes": codex.MONTHLY_LIMIT_MIN, "runs": 9}
        with self.assertRaises(codex.CodexUnavailable):
            self.run_codex()
        self.assertEqual(self.gh.dispatches, [])

    def test_failed_run_falls_out_fast(self):
        self.gh.out_after = 10 ** 6
        self.gh.run_state = "failed"
        with self.assertRaises(codex.CodexUnavailable):
            self.run_codex()

    def test_timeout(self):
        self.gh.out_after = 10 ** 6
        codex.TOTAL_TIMEOUT = -1
        with self.assertRaises(codex.CodexUnavailable):
            self.run_codex()

    def test_prompt_contains_conversation(self):
        p = codex.build_prompt([{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}])
        self.assertIn("User: a", p)
        self.assertIn("Assistant: b", p)


class RouterCodexTest(unittest.TestCase):
    def tearDown(self):
        httpx.AsyncClient = REAL_CLIENT

    def route(self, mode, fake_codex):
        patch(lambda req: httpx.Response(200, text='data: {"choices":[{"delta":{"content":"n"}}]}\n\ndata: [DONE]\n\n'))
        orig = router.codex.run
        router.codex.run = fake_codex
        try:
            return asyncio.run(collect(router.route([{"role": "user", "content": "q"}], mode)))
        finally:
            router.codex.run = orig

    def test_easy_never_uses_codex(self):
        def boom(*a, **k):
            raise AssertionError("easy question must not start an Actions run")
        out = self.route("easy", boom)
        self.assertEqual(out[0], ("model", router.GROQ_MODEL))

    def test_hard_uses_codex_with_model_order(self):
        seen = {}

        async def fake(messages, models):
            seen["models"] = models
            yield "model", "gpt-6-luna"
            yield "delta", "from codex"

        out = self.route("hard", fake)
        self.assertEqual(seen["models"], ["gpt-6-luna", "gpt-5.6-terra", "gpt-5.6-luna"])
        self.assertEqual(out, [("model", "gpt-6-luna"), ("delta", "from codex")])

    def test_codex_failure_falls_to_nvidia_with_notice(self):
        async def fake(messages, models):
            raise codex.CodexUnavailable("x")
            yield

        out = self.route("hard", fake)
        self.assertEqual(out[0], ("notice", "Codex를 쓸 수 없어서 다른 모델로 답해요."))
        self.assertEqual(out[1], ("model", router.NVIDIA_MODELS[0]))

    def test_direct_codex_model_runs_only_that_model(self):
        seen = {}

        async def fake(messages, models):
            seen["models"] = models
            yield "delta", "x"

        self.route("gpt-5.6-terra", fake)
        self.assertEqual(seen["models"], ["gpt-5.6-terra"])


if __name__ == "__main__":
    unittest.main()
