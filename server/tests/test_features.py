"""Projects, artifacts, auto titles and memory suggestions."""
import asyncio
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
os.environ["HARU_DISABLE_LLM"] = "1"
os.environ.setdefault("CRED_FILE", str(Path(tempfile.mkdtemp()) / "creds.json"))
os.environ["GITHUB_TOKEN"] = "x"

from fastapi.testclient import TestClient  # noqa: E402

import artifacts  # noqa: E402
import llm  # noqa: E402
import main  # noqa: E402
import memory  # noqa: E402
import projects  # noqa: E402
import storage  # noqa: E402
from test_router_storage import FakeGitHub, REAL_CLIENT, patch_client  # noqa: E402

HTML_ANSWER = "Here you go:\n```html\n<title>Counter</title>\n<button>+</button>\n```\nEnjoy."
LONG_PY = "```python\n" + "\n".join(f"x{i} = {i}" for i in range(12)) + "\n```"


def client():
    c = TestClient(main.app)
    c.headers["Authorization"] = f"Bearer {main._sign(int(time.time()) + 60)}"
    return c


def reset():
    projects._idx, artifacts._idx, memory._mem, storage._index = None, None, None, None
    projects._cache.clear()
    artifacts._pending_files.clear()
    artifacts._pending_meta.clear()


class ProjectsTest(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGitHub()
        patch_client(self.gh)
        reset()

    def tearDown(self):
        httpx.AsyncClient = REAL_CLIENT
        reset()

    def test_crud_one_commit_each_with_index(self):
        c = client()
        p = c.post("/projects", json={"name": "Trip", "instructions": "Answer briefly",
                                      "files": [{"name": "plan.md", "content": "Day 1: Seoul"}]}).json()
        self.assertTrue(projects.valid_id(p["id"]))
        self.assertEqual({e["path"] for e in self.gh.commits[0]}, {f".agent/projects/{p['id']}.json", projects.INDEX_PATH})
        self.assertEqual(c.get("/projects").json()["projects"][0]["files"], ["plan.md"])
        projects._cache.clear()  # force a read from the store
        self.assertEqual(c.get(f"/projects/{p['id']}").json()["files"][0]["content"], "Day 1: Seoul")
        u = c.put(f"/projects/{p['id']}", json={"name": "Trip 2025"}).json()
        self.assertEqual((u["name"], u["instructions"]), ("Trip 2025", "Answer briefly"))
        a = c.post(f"/projects/{p['id']}/files", json={"name": "plan.md", "content": "Day 1: Busan"}).json()
        self.assertEqual([(f["name"], f["content"]) for f in a["files"]], [("plan.md", "Day 1: Busan")])  # replaced
        c.post(f"/projects/{p['id']}/files", json={"name": "b.txt", "content": "b"})
        self.assertEqual(len(c.delete(f"/projects/{p['id']}/files/b.txt").json()["files"]), 1)
        self.assertEqual(c.delete(f"/projects/{p['id']}/files/nope.txt").status_code, 404)
        self.assertEqual(c.delete(f"/projects/{p['id']}").json(), {"ok": True})
        self.assertNotIn(f".agent/projects/{p['id']}.json", self.gh.files)
        self.assertEqual(json.loads(self.gh.files[projects.INDEX_PATH])["projects"], [])
        self.assertEqual(c.get(f"/projects/{p['id']}").status_code, 404)

    def test_validation_auth_and_rollback(self):
        c = client()
        self.assertEqual(c.post("/projects", json={"name": ""}).status_code, 400)
        self.assertEqual(c.post("/projects", json={"name": "x", "files": [{"name": "a/b", "content": "x"}]}).status_code, 400)
        self.assertEqual(c.post("/projects", json={"name": "x", "files": [{"name": "a", "content": "x" * 20001}]}).status_code, 413)
        too_many = [{"name": f"f{i}", "content": "x"} for i in range(11)]
        self.assertEqual(c.post("/projects", json={"name": "x", "files": too_many}).status_code, 413)
        self.assertEqual(c.get("/projects/..%2Fx").status_code, 404)
        self.assertEqual(TestClient(main.app).get("/projects").status_code, 401)
        self.assertEqual(TestClient(main.app).delete("/projects/abc-123").status_code, 401)
        self.gh.down = True
        self.assertEqual(c.post("/projects", json={"name": "x"}).status_code, 502)
        self.gh.down = False
        self.assertEqual(c.get("/projects").json(), {"projects": []})

    def test_prompt_message_is_capped(self):
        p = {"name": "P", "instructions": "Be brief", "files": [{"name": f"f{i}", "content": "y" * 20000} for i in range(5)]}
        msg = projects.prompt_message(p)
        self.assertLessEqual(len(msg["content"]), projects.PROMPT_CHARS + 600)
        self.assertIn("Be brief", msg["content"])
        self.assertIn("left out", msg["content"])


class ChatWithProjectTest(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGitHub()
        patch_client(self.gh)
        reset()
        memory._mem = {}
        self.seen, self.state = {}, (False, "")

        async def route(messages, mode, effort=""):
            self.seen["m"] = messages
            yield "model", "m1"
            yield "delta", self.seen.get("answer", "ok")

        async def state(chat_id):
            return self.state

        self.orig = (main.router.route, main._chat_state)
        main.router.route, main._chat_state = route, state

    def tearDown(self):
        main.router.route, main._chat_state = self.orig
        httpx.AsyncClient = REAL_CLIENT
        reset()
        memory._mem = {}

    def post(self, **extra):
        return client().post("/chat", json={"chat_id": "c1", "messages": [{"role": "user", "content": "hi"}], **extra})

    def done(self, r):
        return json.loads(r.text.split("event: done\ndata: ")[1].split("\n")[0])

    def test_project_instructions_and_files_reach_the_model_and_stick_to_the_chat(self):
        p = asyncio.run(projects.create("Trip", "Answer in French", [{"name": "plan.md", "content": "Day 1: Seoul"}]))
        d = self.done(self.post(project_id=p["id"]))
        self.assertEqual(d["project_id"], p["id"])
        sysmsg = self.seen["m"][0]["content"]
        self.assertIn("Answer in French", sysmsg)
        self.assertIn("Day 1: Seoul", sysmsg)
        self.assertEqual(asyncio.run(storage.list_chats(project_id=p["id"]))[0]["id"], "c1")
        self.assertEqual(asyncio.run(storage.list_chats(project_id="other-123")), [])
        # next message of the same chat: no project_id sent, the stored one is used
        self.seen.clear()
        self.state = (True, p["id"])
        self.post()
        self.assertIn("Answer in French", self.seen["m"][0]["content"])

    def test_deleted_project_is_ignored_and_bad_id_dropped(self):
        d = self.done(self.post(project_id="gone-123"))
        self.assertIsNone(d["project_id"])
        self.assertEqual(self.seen["m"], [{"role": "user", "content": "hi"}])
        self.assertIsNone(self.done(self.post(project_id="../etc"))["project_id"])


class ArtifactsTest(unittest.TestCase):
    def setUp(self):
        self.gh = FakeGitHub()
        patch_client(self.gh)
        reset()

    def tearDown(self):
        httpx.AsyncClient = REAL_CLIENT
        reset()

    def test_extract_rules(self):
        found = artifacts.extract(HTML_ANSWER + "\n```python\nprint(1)\n```\n" + LONG_PY + "\n```\nplain\n```")
        self.assertEqual([(a["language"], a["title"]) for a in found], [("html", "Counter"), ("python", "python snippet")])
        many = "\n".join(f"```html\n<p>{i}</p>\n```" for i in range(9))
        self.assertEqual(len(artifacts.extract(many)), artifacts.MAX_PER_ANSWER)
        self.assertEqual(artifacts.extract("no code here"), [])

    def test_save_is_one_commit_deduped_listed_read_and_deleted(self):
        metas, saved = asyncio.run(artifacts.save("chat-1", HTML_ANSWER))
        self.assertTrue(saved)
        self.assertEqual(len(self.gh.commits), 1)
        self.assertEqual({e["path"] for e in self.gh.commits[0]}, {f".agent/artifacts/{metas[0]['id']}.json", artifacts.INDEX_PATH})
        again, _ = asyncio.run(artifacts.save("chat-1", HTML_ANSWER))  # regenerated answer, same block
        self.assertEqual((again, len(self.gh.commits)), ([], 1))
        asyncio.run(artifacts.save("chat-2", HTML_ANSWER))  # same code in another chat is a separate artifact
        c = client()
        self.assertEqual(len(c.get("/artifacts").json()["artifacts"]), 2)
        self.assertEqual(len(c.get("/artifacts?chat_id=chat-1").json()["artifacts"]), 1)
        a = c.get(f"/artifacts/{metas[0]['id']}").json()
        self.assertIn("<button>+</button>", a["content"])
        self.assertEqual((a["language"], a["title"]), ("html", "Counter"))
        self.assertEqual(c.delete(f"/artifacts/{metas[0]['id']}").json(), {"ok": True})
        self.assertEqual(c.get(f"/artifacts/{metas[0]['id']}").status_code, 404)
        self.assertEqual(c.get("/artifacts/..%2Fx").status_code, 404)
        self.assertEqual(TestClient(main.app).get("/artifacts").status_code, 401)

    def test_failed_commit_is_retried_with_the_next_one(self):
        self.gh.down = True
        metas, saved = asyncio.run(artifacts.save("chat-1", HTML_ANSWER))
        self.assertFalse(saved)
        self.assertEqual(len(artifacts._pending_files), 1)
        self.gh.down = False
        asyncio.run(artifacts.save("chat-1", "```html\n<p>second</p>\n```"))
        paths = {e["path"] for e in self.gh.commits[-1]}
        self.assertIn(f".agent/artifacts/{metas[0]['id']}.json", paths)  # the earlier one rides along
        self.assertEqual(artifacts._pending_files, {})

    def test_unreadable_index_never_overwrites_the_real_one(self):
        asyncio.run(artifacts.save("chat-1", HTML_ANSWER))
        artifacts._idx = None
        self.gh.fail_index_read = True
        _, saved = asyncio.run(artifacts.save("chat-1", "```html\n<p>new</p>\n```"))
        self.assertFalse(saved)
        self.assertEqual(len(self.gh.commits), 1)  # nothing was written
        self.gh.fail_index_read = False
        asyncio.run(artifacts.save("chat-1", "```html\n<p>later</p>\n```"))
        ids = {m["id"] for m in json.loads(self.gh.files[artifacts.INDEX_PATH])["artifacts"]}
        self.assertEqual(len(ids), 3)  # old + the one that waited + the new one


class ChatFlowTest(unittest.TestCase):
    """Title, memory suggestion and artifacts through POST /chat."""

    def setUp(self):
        self.gh = FakeGitHub()
        patch_client(self.gh)
        reset()
        memory._mem = None
        self.answer, self.saved, self.state = "ok", {}, (False, "")

        async def route(messages, mode, effort=""):
            yield "model", "m1"
            yield "delta", self.answer

        async def save(cid, data, **kw):
            self.saved.update(kw=kw, data=data)
            return True, {"id": cid, "title": kw.get("title") or "fallback"}

        async def state(chat_id):
            return self.state

        self.orig = (main.router.route, main.storage.save_chat, main._chat_state, llm.ask)
        main.router.route, main.storage.save_chat, main._chat_state = route, save, state

    def tearDown(self):
        main.router.route, main.storage.save_chat, main._chat_state, llm.ask = self.orig
        httpx.AsyncClient = REAL_CLIENT
        reset()
        memory._mem = {}

    def post(self, text="hi", **extra):
        return client().post("/chat", json={"chat_id": "c1", "messages": [{"role": "user", "content": text}], **extra})

    def done(self, r):
        return json.loads(r.text.split("event: done\ndata: ")[1].split("\n")[0])

    def fake_llm(self, replies):
        calls = []

        async def ask(system, user, max_tokens=200, timeout=8.0):
            calls.append(system[:20])
            return replies.pop(0) if replies else None

        llm.ask = ask
        return calls

    def test_title_is_generated_for_a_new_chat_only(self):
        calls = self.fake_llm(['"Quicksort 설명."'])
        r = self.post("퀵소트 알려줘")
        self.assertEqual(self.done(r)["title"], "Quicksort 설명")
        self.assertEqual(self.saved["kw"]["title"], "Quicksort 설명")
        self.assertEqual(len(calls), 1)
        self.state = (True, "")  # chat already exists: no second title call
        calls.clear()
        self.post("another")
        self.assertEqual(calls, [])
        self.assertEqual(self.saved["kw"]["title"], "")

    def test_title_failure_falls_back(self):
        self.fake_llm([None])
        self.assertEqual(self.done(self.post("hello there"))["title"], "fallback")

    def test_make_title_cleans_output(self):
        async def ask(*a, **k):
            return "  “오늘의 날씨”\n(extra line)"
        llm.ask = ask
        self.assertEqual(asyncio.run(llm.make_title("q", "a")), "오늘의 날씨")

    def test_memory_suggestion_saves_and_notifies(self):
        self.state = (True, "")  # existing chat: only the memory call uses the LLM
        calls = self.fake_llm([json.dumps({"remember": True, "topic": "Diet", "content": "The user is vegetarian."}), None])
        r = self.post("나는 채식주의자야")
        self.assertIn("기억 업데이트됨", r.text)
        self.assertEqual(asyncio.run(memory.list_all())[0]["content"], "The user is vegetarian.")
        # same topic again -> updated, not duplicated
        self.fake_llm([json.dumps({"remember": True, "topic": "diet", "content": "Vegan since 2025."}), None])
        self.post("나는 이제 비건이야")
        mems = asyncio.run(memory.list_all())
        self.assertEqual((len(mems), mems[0]["content"]), (1, "Vegan since 2025."))

    def test_memory_suggestion_gates_filters_and_respects_temporary(self):
        self.state = (True, "")
        calls = self.fake_llm([json.dumps({"remember": True, "topic": "Diet", "content": "x"})] * 5)
        r = self.post("오늘 서울 날씨 알려줘")  # not about the user: no LLM call for memory
        self.assertNotIn("기억 업데이트됨", r.text)
        self.assertEqual(len(asyncio.run(memory.list_all())), 0)
        self.fake_llm([json.dumps({"remember": True, "topic": "Login", "content": "my password is hunter2hunter2"})])
        self.assertNotIn("기억 업데이트됨", self.post("내 비밀번호는 hunter2hunter2야").text)
        self.fake_llm([json.dumps({"remember": False})])
        self.assertNotIn("기억 업데이트됨", self.post("나는 오늘 피곤해").text)
        calls = self.fake_llm([json.dumps({"remember": True, "topic": "Diet", "content": "vegetarian"})])
        self.assertNotIn("기억 업데이트됨", self.post("나는 채식주의자야", temporary=True).text)
        self.assertEqual(calls, [])  # temporary chats never call the LLM for memory
        self.assertEqual(len(asyncio.run(memory.list_all())), 0)

    def test_explicit_remember_does_not_also_suggest(self):
        self.state = (True, "")
        calls = self.fake_llm([])
        r = self.post("기억해줘: 나는 매운 음식을 좋아해")
        self.assertIn("기억했어요", r.text)
        self.assertNotIn("기억 업데이트됨", r.text)
        self.assertEqual(calls, [])

    def test_artifacts_saved_and_reported_in_done(self):
        self.answer = HTML_ANSWER
        d = self.done(self.post("make a counter"))
        self.assertEqual([(a["language"], a["title"]) for a in d["artifacts"]], [("html", "Counter")])
        self.assertEqual(len(json.loads(self.gh.files[artifacts.INDEX_PATH])["artifacts"]), 1)
        self.assertEqual(self.done(self.post("make a counter", temporary=True))["artifacts"], [])
        self.assertEqual(len(self.gh.commits), 1)  # the temporary chat wrote nothing


class LlmAskTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("HARU_DISABLE_LLM", None)
        os.environ["GROQ_API_KEY"] = "x"
        import usage
        usage._state = None
        usage.USAGE_FILE = Path(tempfile.mkdtemp()) / "u.json"

    def tearDown(self):
        os.environ["HARU_DISABLE_LLM"] = "1"
        httpx.AsyncClient = REAL_CLIENT

    def test_returns_text_none_on_429_and_none_when_disabled(self):
        patch_client(lambda req: httpx.Response(200, json={"choices": [{"message": {"content": " hi "}}]}))
        self.assertEqual(asyncio.run(llm.ask("s", "u")), "hi")
        patch_client(lambda req: httpx.Response(429))
        self.assertIsNone(asyncio.run(llm.ask("s", "u")))
        import usage
        self.assertEqual(usage.snapshot()["groq"]["rate_limited_today"], 1)
        patch_client(lambda req: httpx.Response(500))
        self.assertIsNone(asyncio.run(llm.ask("s", "u")))
        os.environ["HARU_DISABLE_LLM"] = "1"
        self.assertIsNone(asyncio.run(llm.ask("s", "u")))

    def test_parse_json(self):
        self.assertEqual(llm.parse_json('sure: {"a": 1} done'), {"a": 1})
        self.assertIsNone(llm.parse_json("no json"))
        self.assertIsNone(llm.parse_json(None))


if __name__ == "__main__":
    unittest.main()
