"""Stuck tasks are failed by the sweeper; /worker/next and the worker leave timing lines."""
import asyncio
import contextlib
import io
import os
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_main import main, TestClient, haru_worker  # noqa: E402  (also sets the test environment)
from test_worker_loop import FakeServer, http_error  # noqa: E402

tasks = main.task_queue
W = haru_worker


def make_task(content="stuck"):
    return asyncio.run(tasks.create(content, "auto", "c-stuck"))


class SweepTest(unittest.TestCase):
    def setUp(self):
        for d in (tasks.TASKS, tasks.EVENTS, tasks.WORKERS):
            d.clear()
        os.environ["WORKER_TOKEN"] = "stuck-tests"
        self.client = TestClient(main.app)
        self.client.headers["X-Worker-Token"] = "stuck-tests"

    def tearDown(self):
        for d in (tasks.TASKS, tasks.EVENTS, tasks.WORKERS):
            d.clear()
        os.environ.pop("WORKER_TOKEN", None)

    def running(self, age):
        task = make_task()
        asyncio.run(tasks.claim("tab-1"))
        task["heartbeat"] = task["worker_seen"] = time.time() - age
        return task

    def failed_event(self, task):
        return [e["data"] for e in tasks.EVENTS[task["id"]] if e["event"] == "failed"]

    def test_running_without_a_sign_of_life_for_five_minutes_fails(self):
        task = self.running(age=301)
        self.assertEqual(tasks.sweep(), [(task["id"], "일꾼 응답 없음")])
        self.assertEqual(task["status"], "failed")
        self.assertEqual(self.failed_event(task)[0]["error"], "일꾼 응답 없음")
        self.assertIsNotNone(task["finished_at"])

    def test_running_with_recent_heartbeat_or_worker_event_is_left_alone(self):
        self.assertEqual(tasks.sweep(), [])
        fresh = self.running(age=100)
        self.assertEqual(tasks.sweep(), [])
        self.assertEqual(fresh["status"], "running")
        old_beat = self.running(age=400)
        old_beat["worker_seen"] = time.time() - 10  # a worker event (e.g. /worker/next) counts as a sign of life
        self.assertEqual(tasks.sweep(), [])

    def test_queued_for_more_than_ten_minutes_fails_with_its_own_reason(self):
        old, young = make_task("old"), make_task("young")
        old["queued_at"] = time.time() - 601
        young["queued_at"] = time.time() - 300
        self.assertEqual(tasks.sweep(), [(old["id"], "일할 컴퓨터가 받지 않음")])
        self.assertEqual((old["status"], young["status"]), ("failed", "queued"))
        self.assertEqual(self.failed_event(old)[0]["error"], "일할 컴퓨터가 받지 않음")

    def test_a_rewound_task_counts_from_when_it_was_queued_again(self):
        task = make_task()
        task["created"] = time.time() - 3600
        task["queued_at"] = time.time()
        self.assertEqual(tasks.sweep(), [])

    def test_sweeping_twice_changes_nothing_more(self):
        self.running(age=999)
        self.assertEqual(len(tasks.sweep()), 1)
        self.assertEqual(tasks.sweep(), [])
        task = next(iter(tasks.TASKS.values()))
        self.assertEqual(len(self.failed_event(task)), 1)

    def test_late_worker_calls_do_not_resurrect_a_failed_task(self):
        task = self.running(age=999)
        tasks.sweep()
        r = self.client.get("/worker/events", params={"task_id": task["id"]})
        self.assertTrue(r.json()["stopped"])
        r = self.client.post("/worker/done", json={"task_id": task["id"], "result": "late"})
        self.assertEqual(r.json()["status"], "failed")
        self.assertEqual(task["status"], "failed")

    def test_sweep_once_logs_a_warning(self):
        self.running(age=999)
        with self.assertLogs("uvicorn.error", level="WARNING") as cap:
            main._sweep_once()
        self.assertIn("일꾼 응답 없음", " ".join(cap.output))


class ModelTimingLogTest(unittest.TestCase):
    def setUp(self):
        os.environ["WORKER_TOKEN"] = "timing-tests"
        self.client = TestClient(main.app)
        self.client.headers["X-Worker-Token"] = "timing-tests"
        self.orig = main.router.route
        self.replies = []
        outer = self

        async def route(messages, mode, effort=""):
            reply = outer.replies.pop(0) if outer.replies else ""
            if isinstance(reply, tuple):
                await asyncio.sleep(reply[1])
                reply = "{}"
            if isinstance(reply, Exception):
                raise reply
            if reply:
                yield "model", "fake-model"
                yield "delta", reply

        main.router.route = route

    def tearDown(self):
        main.router.route = self.orig
        os.environ.pop("WORKER_TOKEN", None)

    def post(self):
        task = make_task("timing")
        with self.assertLogs("uvicorn.error", level="INFO") as cap:
            r = self.client.post("/worker/next", json={"task_id": task["id"], "history": []})
        return r, [line for line in cap.output if "worker/next model=" in line]

    def test_ok_call_logs_model_seconds_and_result(self):
        self.replies = ['{"action":"command","command":"ls","todos":["a"],"progress":0}']
        r, lines = self.post()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(lines), 1)
        self.assertRegex(lines[0], r"worker/next model=fake-model 걸린초=\d+\.\d 결과=ok")

    def test_each_fallback_is_logged_with_its_own_result(self):
        self.replies = ["garbage", "garbage", '{"action":"done","summary":"ok","progress":1}']
        r, lines = self.post()
        results = [re.search(r"결과=(\S+)", line).group(1) for line in lines]
        self.assertEqual(r.status_code, 200)
        self.assertEqual(results[0], "format_error")
        self.assertEqual(results[-1], "ok")
        self.assertGreaterEqual(len(results), 2)

    def test_a_provider_error_is_logged_as_error(self):
        self.replies = [RuntimeError("boom")] * 4
        r, lines = self.post()
        self.assertTrue(lines)
        self.assertTrue(all("결과=error" in line for line in lines))

    def test_a_timeout_is_logged_as_timeout(self):
        orig = main.WORKER_MODEL_TIMEOUT
        main.WORKER_MODEL_TIMEOUT = 0.05
        self.replies = [("sleep", 1)]
        try:
            r, lines = self.post()
        finally:
            main.WORKER_MODEL_TIMEOUT = orig
        self.assertEqual(r.status_code, 503)
        self.assertTrue(any("결과=timeout" in line for line in lines))


class WorkerTimingLogTest(unittest.TestCase):
    LINE = re.compile(r"^\[\d\d:\d\d:\d\d\] .+")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = Path(self.tmp.name) / "src"
        self.src.mkdir()
        self.orig = (W.ROOT, W.SOURCE, W.api, W.NEXT_RETRY_WAIT)
        W.NEXT_RETRY_WAIT = 0
        W.ROOT, W.SOURCE = Path(self.tmp.name) / "work", self.src

    def tearDown(self):
        W.ROOT, W.SOURCE, W.api, W.NEXT_RETRY_WAIT = self.orig
        self.tmp.cleanup()

    def handle(self, server):
        calls = []
        base = server.api

        def api(path, body=None, method="POST", **kw):
            calls.append(path)
            if path == "/worker/done":
                return {"ok": True}
            return base(path, body, method, **kw)

        W.api = api
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            W.handle_task({"id": "timing01abcdef", "content": "x", "mode": "auto", "checkpoint": None})
        return out.getvalue(), calls

    def test_every_phase_leaves_one_line_without_secrets_or_output(self):
        secret_output = "SECRET-OUTPUT-" + "z" * 8
        server = FakeServer([
            {"action": "command", "command": f"echo {secret_output}", "label": "x", "todos": [{"id": "t1", "text": "a", "done": False}]},
            {"action": "done", "summary": "ok"},
        ])
        text, calls = self.handle(server)
        for needle in ("작업 받음", "next 요청 (단계 1)", "next 응답 (단계 1)", "HTTP 200", "재시도 0회", "명령 실행", "done 보고"):
            self.assertIn(needle, text)
        self.assertTrue(all(self.LINE.match(line) for line in text.splitlines() if line.startswith("[")))
        self.assertRegex(text, r"명령 실행 · \d+\.\d초")
        self.assertNotIn(secret_output, text)
        self.assertEqual(calls[-1], "/worker/done")

    def test_retries_are_counted_in_the_timing_lines(self):
        server = FakeServer([{"action": "done", "summary": "ok"}])
        server.next_failures = [http_error(502), http_error(503)]
        text, _ = self.handle(server)
        self.assertIn("next 시도 실패 (단계 1)", text)
        self.assertIn("HTTP 502", text)
        self.assertIn("재시도 2회", text)  # answered on the third try

    def test_a_failed_task_is_still_timed_and_reported(self):
        server = FakeServer([])
        server.next_failures = [http_error(502)] * 4
        text, calls = self.handle(server)
        self.assertIn("next 실패 (단계 1)", text)
        self.assertIn("done 보고", text)
        self.assertEqual(calls[-1], "/worker/done")


if __name__ == "__main__":
    unittest.main()
