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
        self.prompts, self.modes, self.replies, self.messages = [], [], [], []
        outer = self

        async def route(messages, mode, effort=""):
            outer.prompts.append(messages[0]["content"])
            outer.messages.append(list(messages))
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
        self.messages.clear()
        self.assertEqual(self.post(task, history=[]).json()["action"], "done")
        self.assertEqual(len(self.prompts), 2)
        asked_again = self.messages[1]  # the same conversation: question, the bad reply, then the reminder
        self.assertEqual([m["role"] for m in asked_again], ["user", "assistant", "user"])
        self.assertEqual(asked_again[1]["content"], "not json at all")
        self.assertIn("JSON 객체 하나로만 답해", asked_again[2]["content"])

    def test_invalid_everywhere_is_502_and_no_model_is_503(self):
        task = make_task()
        self.replies = ["garbage"] * 4  # Groq twice, then NVIDIA twice
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

    # ---- reading the reply generously ----
    def test_reply_with_text_and_fences_around_the_json_is_used(self):
        task = make_task()
        self.replies = ['네, 이렇게 하겠습니다!\n```json\n{"action":"command","command":"ls","label":"목록"}\n```\n위 명령을 실행해 주세요.']
        d = self.post(task, history=[]).json()
        self.assertEqual((d["action"], d["command"], d["label"]), ("command", "ls", "목록"))
        self.assertEqual(len(self.prompts), 1)  # no retry needed

    def test_common_variants_of_the_shape_are_accepted(self):
        task = make_task()
        cases = [
            ('{"Action":"Command","Command":["ls","-la","docs dir"]}', ("command", "ls -la 'docs dir'")),  # key case, argv array
            ('{"type":"run","cmd":"head -n 3 SPEC.md"}', ("command", "head -n 3 SPEC.md")),  # type/cmd names
            ('{"command":"pwd"}', ("command", "pwd")),  # no action key at all
            ('{"action":{"type":"command","command":"ls"}}', ("command", "ls")),  # nested action object
            ('{"actions":[{"action":"command","command":"cat README.md"}]}', ("command", "cat README.md")),
            ('{"next_action":{"type":"finish","result":"요약 끝"}}', ("done", "요약 끝")),  # wrapper, finish/result names
            ('예시: {"foo": 1}\n실제: {"action":"done","summary":"끝"}', ("done", "끝")),  # an unrelated object first
            ('{"action":"command","command":"echo }"}', ("command", "echo }")),  # a brace inside a string
            ('{"action":"reply","message":"설명입니다"}', ("answer", "설명입니다")),
        ]
        for reply, (kind, value) in cases:
            self.replies = [reply]
            d = self.post(task, history=[]).json()
            self.assertEqual(d["action"], kind, reply)
            self.assertEqual(d.get("command") or d.get("text") or d.get("summary"), value, reply)

    # ---- retry and fallback ----
    def test_first_reply_unreadable_then_retry_in_the_same_conversation_works(self):
        task = make_task()
        self.replies = ["죄송합니다, 먼저 파일을 확인해 볼게요.", '{"action":"command","command":"ls"}']
        d = self.post(task, history=[])
        self.assertEqual(d.status_code, 200)
        self.assertEqual(d.json()["command"], "ls")
        self.assertEqual(self.modes, ["easy", "easy"])

    def test_groq_unreadable_twice_then_nvidia_answers(self):
        task = make_task()
        self.replies = ["not json", "still not json", '{"action":"command","command":"ls"}']
        d = self.post(task, history=[])
        self.assertEqual(d.status_code, 200, d.text)
        self.assertEqual(d.json()["command"], "ls")
        self.assertEqual(self.modes[:2], ["easy", "easy"])
        self.assertTrue(self.modes[2].startswith("nvidia/"), self.modes)  # Groq is skipped
        self.assertEqual(self.messages[2][-1]["role"], "user")  # asked in the same conversation

    def test_an_empty_first_reply_is_retried_too(self):
        task = make_task()
        self.replies = ["", '{"action":"done","summary":"끝"}']
        self.assertEqual(self.post(task, history=[]).json()["action"], "done")
        self.assertEqual(self.messages[1][1]["content"], "(empty)")

    # ---- the log says why ----
    def test_final_failure_is_logged_with_reason_and_masked_head(self):
        task = make_task()
        os.environ["GROQ_API_KEY"] = "my-groq-value-123456"
        fake_key = "gsk" + "_" + "abcdefghijklmnop1234"  # built at run time so the source has no key-like text
        self.replies = [fake_key + " and my-groq-value-123456 are not json " + "x" * 500] * 4
        try:
            with self.assertLogs("uvicorn.error", level="WARNING") as cap:
                r = self.post(task, history=[])
        finally:
            os.environ.pop("GROQ_API_KEY", None)
        self.assertEqual(r.status_code, 502)
        line = " ".join(cap.output)
        self.assertIn("worker next failed", line)
        self.assertIn("형식 오류", line)
        self.assertIn("NVIDIA", line)  # the tries are listed
        self.assertIn("***", line)
        self.assertNotIn(fake_key, line)
        self.assertNotIn("my-groq-value-123456", line)
        head = line.split("reply_head=")[1]
        self.assertLessEqual(len(head), 400)  # about 300 characters of the reply

    def test_empty_everywhere_and_timeout_are_logged_with_their_reason(self):
        task = make_task()
        self.replies = []
        with self.assertLogs("uvicorn.error", level="WARNING") as cap:
            self.assertEqual(self.post(task, history=[]).status_code, 503)
        self.assertIn("빈 답", " ".join(cap.output))
        orig = main.WORKER_MODEL_TIMEOUT
        main.WORKER_MODEL_TIMEOUT = 0.05
        self.replies = [("sleep", 1)]
        try:
            with self.assertLogs("uvicorn.error", level="WARNING") as cap:
                self.assertEqual(self.post(task, history=[]).status_code, 503)
        finally:
            main.WORKER_MODEL_TIMEOUT = orig
        self.assertIn("시간 초과", " ".join(cap.output))

    def test_long_outputs_are_cut_before_they_go_to_the_model(self):
        task = make_task()
        self.replies = ['{"action":"done","summary":"ok"}']
        self.post(task, history=[{"kind": "command", "command": "cat SPEC.md", "output": "가" * 6000}])
        self.assertIn("총 6000자", self.prompts[0])
        self.assertLess(len(self.prompts[0]), 6500)

    def test_mask_secrets_hides_keys_and_bearer_tokens(self):
        masked = agent_loop.mask_secrets("Bear" + "er abcdefghijklmnop nvapi" + "-abcdefghij1234 github" + "_pat_abcdefghijk 123456789:" + "A" * 35)
        self.assertNotIn("abcdefghij", masked)
        self.assertEqual(masked.count("***"), 4)

    # ---- one answer at most, no invention, line breaks ----
    def test_after_an_answer_the_prompt_demands_done_and_a_second_answer_becomes_the_summary(self):
        task = make_task()
        answered = [{"kind": "command", "command": "head -n 3 SPEC.md", "output": "첫째\n둘째\n셋째"}, {"kind": "answer", "text": "세 줄 요약입니다."}]
        self.replies = ['{"action":"answer","text":"또 다른 답변\\n두 번째 줄"}']
        d = self.post(task, history=answered).json()
        self.assertIn("이미 답했다", self.prompts[0])
        self.assertIn("reply with action \"done\" only", self.prompts[0])
        self.assertEqual(d["action"], "done")  # a second answer ends the task with the last answer
        self.assertEqual(d["summary"], "또 다른 답변\n두 번째 줄")
        # a first answer is still allowed, and an empty earlier answer does not count as an answer
        self.replies = ['{"action":"answer","text":"첫 답변"}']
        self.assertEqual(self.post(task, history=[{"kind": "answer", "text": ""}]).json()["action"], "answer")
        self.assertNotIn("이미 답했다", self.prompts[-1])

    def test_the_prompt_says_to_write_only_what_the_outputs_show(self):
        task = make_task()
        self.replies = ['{"action":"done","summary":"ok"}']
        self.post(task, history=[])
        self.assertIn("ONLY what appears in the real command outputs", self.prompts[0])
        self.assertIn("실제 명령 출력에 있는 내용만 쓰고, 없는 건 쓰지 마라", self.prompts[0])
        self.assertIn("line breaks", self.prompts[0])

    def test_multi_line_summary_keeps_its_line_breaks(self):
        task = make_task()
        # escaped line breaks inside the JSON string, a raw line break inside the string, and the two characters backslash+n
        for reply in ('{"action":"done","summary":"1) 첫째\\n2) 둘째\\n3) 셋째"}',
                      '{"action":"done","summary":"1) 첫째\n2) 둘째\n3) 셋째"}',
                      '{"action":"done","summary":"1) 첫째\\\\n2) 둘째\\\\n3) 셋째"}'):
            self.replies = [reply]
            d = self.post(task, history=[]).json()
            self.assertEqual(d["summary"], "1) 첫째\n2) 둘째\n3) 셋째", reply)
        self.replies = ['{"action":"answer","text":"가\\n나"}']
        self.assertEqual(self.post(task, history=[]).json()["text"], "가\n나")
        self.assertEqual(agent_loop.fix_newlines("C:\\new\\file"), "C:\\new\\file")  # a Windows path is left alone

    def test_extract_json_and_clip_helpers(self):
        self.assertEqual(agent_loop.extract_json('앞 {"a": {"b": 1}} 뒤'), {"a": {"b": 1}})
        self.assertIsNone(agent_loop.extract_json("no braces"))
        self.assertLessEqual(len(agent_loop.clip("y" * 9000)), 1600)
        self.assertIn("중략", agent_loop.clip("y" * 9000))


if __name__ == "__main__":
    unittest.main()
