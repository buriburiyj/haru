"""The worker's loop with a fake server: next action -> run -> output back -> next action ... until "done"."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_main import haru_worker  # noqa: E402  (also puts worker/ on the path)

W = haru_worker


def http_error(code, detail="model returned an invalid action"):
    return urllib.error.HTTPError("http://x/worker/next", code, "err", {}, io.BytesIO(('{"detail":"%s"}' % detail).encode()))


class FakeServer:
    """Stands in for the HTTP API: scripted answers for /worker/next, everything else recorded."""

    def __init__(self, script, mode="auto"):
        self.script = list(script)
        self.mode = mode
        self.next_calls = []
        self.next_attempts = 0
        self.next_failures = []  # exceptions raised by /worker/next before it answers
        self.events = []
        self.permission_asked = []

    def api(self, path, body=None, method="POST", **kw):
        if path.startswith("/worker/events"):
            return {"messages": [], "controls": [], "mode": self.mode, "stopped": False}
        if path == "/worker/event":
            self.events.append((body["event"], body["data"]))
            return {"ok": True}
        if path == "/worker/heartbeat":
            return {"ok": True}
        if path == "/worker/permission":
            self.permission_asked.append(body["command"])
            return {"decision": "deny"}
        if path == "/worker/next":
            self.next_attempts += 1
            if self.next_failures:
                raise self.next_failures.pop(0)
            self.next_calls.append(json.loads(json.dumps(body)))  # what was sent at that moment
            step = self.script.pop(0) if self.script else {"action": "done", "summary": "script ended"}
            return step(body) if callable(step) else step
        raise AssertionError(path)

    def of(self, kind):
        return [d for k, d in self.events if k == kind]


class WorkerLoopTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.src = Path(self.tmp.name) / "src"
        self.src.mkdir()
        (self.src / "README.md").write_text("# Haru 프로젝트\nsecond line\n")
        self.orig = (W.ROOT, W.SOURCE, W.api, W.ISOLATED, W.COMMAND_TIMEOUT, W.NEXT_RETRY_WAIT)
        W.NEXT_RETRY_WAIT = 0
        W.ROOT, W.SOURCE = Path(self.tmp.name) / "work", self.src

    def tearDown(self):
        W.ROOT, W.SOURCE, W.api, W.ISOLATED, W.COMMAND_TIMEOUT, W.NEXT_RETRY_WAIT = self.orig
        self.tmp.cleanup()

    def run_task(self, server, mode="auto", content="README 첫 줄을 요약해줘"):
        W.api = server.api
        task = {"id": "loop-" + str(abs(hash((content, mode, id(server)))))[:6], "content": content, "mode": mode, "checkpoint": None}
        return W.run_task(task)

    # (a) read -> write an answer -> done: three steps, the summary is made after the real output was seen
    def test_read_answer_done_in_three_steps(self):
        server = FakeServer([
            {"action": "command", "command": "ls -la && head -n 1 README.md", "label": "파일 목록과 README 첫 줄", "todos": [{"id": "t1", "text": "읽기", "done": False}, {"id": "t2", "text": "요약", "done": False}], "model": "m"},
            {"action": "answer", "text": "README의 첫 줄은 Haru 프로젝트 제목입니다.", "todos": [{"id": "t1", "text": "읽기", "done": True}, {"id": "t2", "text": "요약", "done": False}]},
            lambda body: {"action": "done", "summary": "확인한 결과: " + ("Haru 프로젝트" if "Haru 프로젝트" in str(body["history"]) else "출력 없음"),
                          "todos": [{"id": "t1", "text": "읽기", "done": True}, {"id": "t2", "text": "요약", "done": True}]},
        ])
        result = self.run_task(server)
        self.assertEqual(result, "확인한 결과: Haru 프로젝트")  # the final summary came after the output was returned to the model
        self.assertEqual(len(server.next_calls), 3)
        self.assertEqual(server.next_calls[0]["history"], [])
        second = server.next_calls[1]["history"]
        self.assertEqual(second[0]["kind"], "command")
        self.assertIn("# Haru 프로젝트", second[0]["output"])
        self.assertEqual([h["kind"] for h in server.next_calls[2]["history"]], ["command", "answer"])
        # events: action running -> done, output, answer rows, todos updated every step, one summary
        actions = server.of("action")
        self.assertEqual([a["status"] for a in actions if a["command"].startswith("ls")], ["running", "done"])
        self.assertTrue(any("# Haru 프로젝트" in o["text"] for o in server.of("output")))
        self.assertTrue(any("제목입니다" in o["text"] for o in server.of("output")))
        todos = server.of("todos")
        self.assertEqual(len(todos), 3)
        self.assertEqual([t["done"] for t in todos[-1]["todos"]], [True, True])
        self.assertEqual(len(server.of("summary")), 1)
        self.assertEqual(server.of("summary")[0]["text"], result)

    # (b) a blocked command is reported to the model with its real reason; the task goes on with another way
    def test_blocked_command_does_not_end_the_task(self):
        server = FakeServer([
            {"action": "command", "command": "rm -rf build", "label": "build 지우기"},
            {"action": "command", "command": 'echo "unclosed', "label": "따옴표 오류"},
            {"action": "command", "command": "cat /etc/passwd", "label": "절대경로"},
            {"action": "command", "command": "python3 run.py", "label": "목록 밖"},
            {"action": "command", "command": "ls", "label": "다른 방법"},
            {"action": "done", "summary": "막힌 것을 피해서 목록을 확인했습니다."},
        ])
        result = self.run_task(server)
        self.assertEqual(result, "막힌 것을 피해서 목록을 확인했습니다.")
        reasons = [d["reason"] for d in server.of("skipped")]
        self.assertEqual(len(reasons), 4)
        self.assertIn("rm", reasons[0])
        self.assertIn("따옴표", reasons[1])
        self.assertIn("절대경로", reasons[2])
        self.assertIn("허용 목록 밖", reasons[3])
        history = server.next_calls[1]["history"]
        self.assertEqual((history[0]["kind"], history[0]["command"]), ("skipped", "rm -rf build"))
        self.assertIn("rm", history[0]["reason"])  # the model is told why
        self.assertEqual(server.next_calls[-1]["history"][-1]["kind"], "command")  # `ls` really ran
        self.assertEqual(server.permission_asked, [])  # blocked commands never reach the user

    def test_the_same_command_blocked_twice_is_refused_without_asking_again(self):
        server = FakeServer([{"action": "command", "command": "rm -rf build"}] * 3 + [{"action": "done", "summary": "ok"}])
        self.run_task(server)
        reasons = [d["reason"] for d in server.of("skipped")]
        self.assertIn("2번 막혔습니다", reasons[2])
        history = server.next_calls[2]["history"]
        self.assertIn("반드시 다른 방법", history[1]["reason"])  # the model is told after the second block

    def test_a_failing_command_is_returned_to_the_model_not_raised(self):
        server = FakeServer([{"action": "command", "command": "cat missing.txt"}, {"action": "command", "command": "head -n 1 README.md"}, {"action": "done", "summary": "ok"}])
        self.assertEqual(self.run_task(server), "ok")
        err = server.of("error")[0]
        self.assertEqual((err["exit_code"], err["reason"]), (1, "command failed"))
        failed = server.next_calls[1]["history"][0]
        self.assertEqual((failed["kind"], failed["exit_code"]), ("error", 1))
        self.assertIn("missing.txt", failed["output"])

    # (c) 15 steps at most, then a last call that must end with a summary
    def test_step_limit_is_fifteen(self):
        server = FakeServer([{"action": "command", "command": "ls"}] * 20)
        result = self.run_task(server)
        self.assertEqual(len([a for a in server.of("action") if a["status"] == "running"]), 15)
        self.assertEqual(len(server.next_calls), 16)
        self.assertTrue(server.next_calls[-1]["force_done"])
        self.assertFalse(server.next_calls[0]["force_done"])
        self.assertTrue(result.startswith("※ 최대 15단계에 도달해 중간에 멈췄습니다."))

    # (d) allow_all: runs what the safety rules allow without asking (isolated computers only)
    def test_allow_all_runs_safe_commands_without_permission(self):
        W.ISOLATED = True
        server = FakeServer([
            {"action": "command", "command": 'python3 -c "print(40+2)"', "label": "파이썬"},
            {"action": "command", "command": "cat .env", "label": ".env 읽기"},
            {"action": "command", "command": "rm -rf x", "label": "삭제"},
            {"action": "done", "summary": "끝"},
        ], mode="allow_all")
        self.run_task(server, mode="allow_all")
        self.assertIn("42", server.of("output")[0]["text"])  # an "unknown" program ran
        self.assertEqual(server.permission_asked, [])  # nothing was asked
        reasons = [d["reason"] for d in server.of("skipped")]
        self.assertIn(".env", reasons[0])  # still blocked
        self.assertIn("rm", reasons[1])  # still blocked

    def test_allow_all_is_ignored_on_a_computer_that_is_not_isolated(self):
        W.ISOLATED = False
        server = FakeServer([{"action": "command", "command": 'python3 -c "print(1)"'}, {"action": "done", "summary": "ok"}], mode="allow_all")
        self.run_task(server, mode="allow_all")
        self.assertEqual(server.of("output"), [])
        self.assertIn("격리된 컴퓨터", server.of("skipped")[0]["reason"])

    def test_auto_mode_still_skips_programs_and_plan_mode_runs_nothing(self):
        server = FakeServer([{"action": "command", "command": 'python3 -c "print(1)"'}, {"action": "done", "summary": "ok"}], mode="auto")
        self.run_task(server)
        self.assertIn("허용 목록 밖", server.of("skipped")[0]["reason"])
        server = FakeServer([{"action": "command", "command": "ls"}, {"action": "done", "summary": "계획"}], mode="plan")
        self.run_task(server, mode="plan", content="plan mode request")
        self.assertIn("계획 모드", server.of("skipped")[0]["reason"])

    def test_check_gives_a_reason_for_every_refusal(self):
        task = {"id": "t", "mode": "auto"}
        for command, word in (("rm -rf x", "rm"), ("cat ../secret", ".."), ("ls /etc", "절대경로"), ('echo "a', "따옴표"), ("cat .env", ".env"), ("node app.js", "허용 목록 밖")):
            allowed, reason = W.check(task, command, "a", "l")
            self.assertFalse(allowed, command)
            self.assertIn(word, reason, command)
        self.assertEqual(W.check(task, "ls -la", "a", "l"), (True, ""))

    def test_a_command_that_runs_too_long_is_stopped_and_reported(self):
        W.COMMAND_TIMEOUT = 1
        server = FakeServer([{"action": "command", "command": "sleep 5"}, {"action": "done", "summary": "ok"}])
        self.run_task(server)
        self.assertEqual(server.of("error")[0]["exit_code"], 124)
        self.assertIn("시간 초과", server.of("error")[0]["output"])

    # ---- /worker/next trouble ----
    def test_a_502_once_then_the_task_goes_on(self):
        server = FakeServer([{"action": "command", "command": "ls"}, {"action": "done", "summary": "ok"}])
        server.next_failures = [http_error(502)]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(self.run_task(server), "ok")
        self.assertEqual(server.next_attempts, 3)  # failed once, then both steps
        self.assertIn("다시 (1/3)", out.getvalue())

    def test_503_504_and_connection_errors_are_asked_again(self):
        for failures in ([http_error(503)], [http_error(504)], [urllib.error.URLError("connection refused")], [OSError("reset")]):
            server = FakeServer([{"action": "done", "summary": "ok"}])
            server.next_failures = failures
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(self.run_task(server, content="retry " + repr(failures)), "ok")

    def test_three_retries_then_the_task_fails_with_a_reason_and_a_log_line(self):
        server = FakeServer([{"action": "done", "summary": "never"}])
        server.next_failures = [http_error(502)] * 4
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(RuntimeError) as cm:
            self.run_task(server)
        self.assertEqual(server.next_attempts, 4)  # 1 + 3 retries
        self.assertIn("모델이 다음 행동을 정하지 못했습니다", str(cm.exception))
        self.assertIn("502", str(cm.exception))
        self.assertIn("3번 다시 물은 뒤", out.getvalue())

    def test_other_http_errors_are_not_retried(self):
        server = FakeServer([{"action": "done", "summary": "never"}])
        server.next_failures = [http_error(400)]
        with self.assertRaises(urllib.error.HTTPError):
            self.run_task(server)
        self.assertEqual(server.next_attempts, 1)

    def test_changed_files_are_listed_in_the_summary_event(self):
        server = FakeServer([{"action": "command", "command": "touch new.txt"}, {"action": "done", "summary": "ok"}], mode="auto_edit")
        self.run_task(server, mode="auto_edit")
        files = server.of("summary")[0]["files"]
        self.assertIn({"path": "new.txt", "change": "added"}, files)


if __name__ == "__main__":
    unittest.main()
