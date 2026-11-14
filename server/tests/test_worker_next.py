"""POST /worker/next: the planner that picks the worker's next action from the history."""
import asyncio
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_main import main, TestClient  # noqa: E402  (also sets the test environment)

import agent_loop  # noqa: E402


def make_task(mode="auto", content="README 첫 줄을 요약해줘"):
    return asyncio.run(main.task_queue.create(content, mode, "c-next"))


class WorkerNextTest(unittest.TestCase):
    def setUp(self):
        os.environ["WORKER_TOKEN"] = "next-tests"
        self.client = TestClient(main.app)
        self.client.headers["X-Worker-Token"] = "next-tests"
        self.orig = main.router.route
        self.prompts, self.modes, self.replies = [], [], []
        outer = self

        async def route(messages, mode, effort=""):
            outer.prompts.append(messages[0]["content"])
            outer.modes.append(mode)
            reply = outer.replies.pop(0) if outer.replies else ""
            if isinstance(reply, tuple):  # ("sleep", seconds): a model that is too slow
                await asyncio.sleep(reply[1])
                reply = "{}"
            if reply:
                yield "model", "fake-model"
                yield "delta", reply

        main.router.route = route

    def tearDown(self):
        main.router.route = self.orig
        os.environ.pop("WORKER_TOKEN", None)

    def post(self, task, **body):
        return self.client.post("/worker/next", json={"task_id": task["id"], **body})

    def test_first_step_returns_command_label_and_todos_and_uses_the_fast_path(self):
        task = make_task()
        self.replies = ['{"action":"command","command":"ls -la && head -n 1 README.md","label":"파일 목록 확인","todos":["파일 목록 확인","README 첫 줄 읽기","한 문장 요약"],"progress":0}']
        r = self.post(task, entries=["README.md"], history=[])
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertEqual((d["action"], d["command"], d["label"], d["model"]), ("command", "ls -la && head -n 1 README.md", "파일 목록 확인", "fake-model"))
        self.assertEqual([t["text"] for t in d["todos"]], ["파일 목록 확인", "README 첫 줄 읽기", "한 문장 요약"])
        self.assertTrue(all(t["done"] is False for t in d["todos"]))
        self.assertEqual(self.modes, ["easy"])  # Groq/NVIDIA only, never a slow Codex run
        self.assertIn("README.md", self.prompts[0])
        self.assertIn("first step", self.prompts[0])

    def test_outputs_and_block_reasons_reach_the_model_and_done_checks_every_todo(self):
        task = make_task()
        self.replies = ['{"action":"command","command":"x","todos":["a","b","c"],"progress":0}']
        self.post(task, history=[])
        history = [
            {"kind": "skipped", "command": "rm -rf build", "reason": "차단된 명령입니다 (rm)"},
            {"kind": "command", "command": "head -n 1 README.md", "output": "# Haru 프로젝트"},
            {"kind": "error", "command": "cat nope.txt", "output": "No such file", "exit_code": 1},
        ]
        self.replies = ['{"action":"done","summary":"첫 줄은 Haru 프로젝트입니다.","progress":3}']
        d = self.post(task, history=history).json()
        self.assertEqual(d["action"], "done")
        self.assertEqual(d["summary"], "첫 줄은 Haru 프로젝트입니다.")
        self.assertTrue(all(t["done"] for t in d["todos"]))
        p = self.prompts[-1]
        for expected in ("SKIPPED", "차단된 명령입니다 (rm)", "# Haru 프로젝트", "FAILED exit 1", "No such file", "Step 4 of at most 15"):
            self.assertIn(expected, p)

    def test_progress_marks_only_that_many_todos(self):
        task = make_task()
        self.replies = ['{"action":"command","command":"ls","todos":["a","b","c","d"],"progress":0}']
        self.post(task, history=[])
        self.replies = ['{"action":"command","command":"ls","progress":2}']
        d = self.post(task, history=[{"kind": "command", "command": "ls", "output": "x"}]).json()
        self.assertEqual([t["done"] for t in d["todos"]], [True, True, False, False])

    def test_fenced_and_chatty_replies_are_accepted_and_garbage_is_retried_once(self):
        task = make_task()
        self.replies = ['여기 있습니다:\n```json\n{"action":"answer","text":"이렇게 정리했습니다"}\n```']
        self.assertEqual(self.post(task, history=[]).json()["action"], "answer")
        self.replies = ["not json at all", '{"action":"done","summary":"끝"}']
        self.prompts.clear()
        self.assertEqual(self.post(task, history=[]).json()["action"], "done")
        self.assertEqual(len(self.prompts), 2)
        self.assertIn("not a valid JSON action", self.prompts[1])

    def test_invalid_twice_is_502_and_no_model_is_503(self):
        task = make_task()
        self.replies = ["garbage", "still garbage"]
        self.assertEqual(self.post(task, history=[]).status_code, 502)
        self.replies = []
        self.assertEqual(self.post(task, history=[]).status_code, 503)

    def test_a_command_blocked_twice_is_not_accepted_again(self):
        task = make_task()
        blocked = {"kind": "skipped", "command": "rm -rf build", "reason": "차단"}
        self.replies = ['{"action":"command","command":"rm -rf build"}', '{"action":"command","command":"ls build"}']
        d = self.post(task, history=[blocked, blocked]).json()
        self.assertEqual(d["command"], "ls build")  # asked again, the second answer is a different way
        self.assertIn("blocked twice", self.prompts[-1])
        self.replies = ['{"action":"command","command":"rm -rf build"}', '{"action":"command","command":"rm -rf build"}']
        d = self.post(task, history=[blocked, blocked]).json()
        self.assertEqual(d["action"], "done")  # no way found: say so instead of looping
        self.assertIn("막힌 명령", d["summary"])

    def test_force_done_turns_any_action_into_the_final_summary(self):
        task = make_task()
        self.replies = ['{"action":"command","command":"ls"}']
        d = self.post(task, history=[{"kind": "command", "command": "ls", "output": "a"}], force_done=True).json()
        self.assertEqual(d["action"], "done")
        self.assertIn("LAST step", self.prompts[0])

    def test_plan_mode_is_told_not_to_run_commands(self):
        task = make_task(mode="plan")
        self.replies = ['{"action":"done","summary":"계획: 1) 읽기 2) 요약"}']
        self.post(task, history=[])
        self.assertIn("PLAN", self.prompts[0])

    def test_the_prompt_stays_small_for_long_histories(self):
        task = make_task()
        history = [{"kind": "command", "command": f"echo {i}", "output": "x" * 5000} for i in range(40)]
        self.replies = ['{"action":"done","summary":"ok"}']
        self.post(task, history=history)
        self.assertIn("earlier 28 steps omitted", self.prompts[0])
        self.assertLess(len(self.prompts[0]), 14000)

    def test_a_slow_model_gives_503_within_the_limit(self):
        task = make_task()
        orig = main.WORKER_MODEL_TIMEOUT
        main.WORKER_MODEL_TIMEOUT = 0.05
        self.replies = [("sleep", 1)]
        try:
            self.assertEqual(self.post(task, history=[]).status_code, 503)
        finally:
            main.WORKER_MODEL_TIMEOUT = orig

    def test_worker_token_and_known_task_are_required(self):
        task = make_task()
        self.assertEqual(TestClient(main.app).post("/worker/next", json={"task_id": task["id"]}).status_code, 401)
        self.assertEqual(self.client.post("/worker/next", json={"task_id": "nope"}).status_code, 404)

    def test_interjection_text_sent_by_the_worker_replaces_the_stored_request(self):
        task = make_task()
        self.replies = ['{"action":"done","summary":"ok"}']
        self.post(task, history=[], content="원래 요청\n\n추가 요청: 한 줄로")
        self.assertIn("추가 요청: 한 줄로", self.prompts[0])

    def test_extract_json_and_clip_helpers(self):
        self.assertEqual(agent_loop.extract_json('앞 {"a": {"b": 1}} 뒤'), {"a": {"b": 1}})
        self.assertIsNone(agent_loop.extract_json("no braces"))
        self.assertLessEqual(len(agent_loop.clip("y" * 9000)), 1600)
        self.assertIn("중략", agent_loop.clip("y" * 9000))


if __name__ == "__main__":
    unittest.main()
