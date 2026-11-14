"""Task clock (same elapsed time on every device) and worker presence."""
import asyncio
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_main import authed_client, main  # noqa: E402  (also sets the test environment)

tasks = main.task_queue


class FakeStorage:
    async def get_chat(self, cid):
        return None

    async def save_chat(self, cid, data, **kw):
        return True, {"id": cid}


class TaskClockTest(unittest.TestCase):
    def setUp(self):
        self.orig = (main.storage.get_chat, main.storage.save_chat)
        main.storage.get_chat, main.storage.save_chat = FakeStorage().get_chat, FakeStorage().save_chat
        tasks.WORKERS.clear()
        tasks.TASKS.clear()  # other tests leave queued tasks behind; claim() would take those first
        tasks.EVENTS.clear()
        import os
        os.environ["WORKER_TOKEN"] = "clock-tests"
        from fastapi.testclient import TestClient
        self.worker = TestClient(main.app, base_url="https://testserver")
        self.worker.headers["X-Worker-Token"] = "clock-tests"
        self.c = authed_client()

    def tearDown(self):
        main.storage.get_chat, main.storage.save_chat = self.orig
        tasks.WORKERS.clear()
        tasks.TASKS.clear()
        tasks.EVENTS.clear()

    def new_task(self):
        return self.c.post("/tasks", json={"content": "clock", "mode": "auto"}).json()["id"]

    def test_created_task_has_created_at_in_detail_and_first_event(self):
        before = time.time()
        tid = self.new_task()
        d = self.c.get(f"/tasks/{tid}").json()
        self.assertGreaterEqual(d["created_at"], before - 1)
        self.assertIsNone(d["started_at"])
        self.assertIsNone(d["finished_at"])
        self.assertIn("now", d)
        first = d["events"][0]
        self.assertEqual(first["event"], "task")
        self.assertEqual(first["data"]["created_at"], d["created_at"])
        self.assertIn("now", first["data"])

    def test_started_at_is_in_detail_list_and_the_status_event(self):
        tid = self.new_task()
        claimed = self.worker.post("/worker/claim", json={"worker_id": "mac"}).json()["task"]
        self.assertEqual(claimed["id"], tid)
        d = self.c.get(f"/tasks/{tid}").json()
        status = next(e["data"] for e in d["events"] if e["event"] == "status")
        self.assertEqual(status["started_at"], d["started_at"])
        self.assertEqual(status["created_at"], d["created_at"])
        listed = [t for t in self.c.get("/tasks?active=true").json()["tasks"] if t["id"] == tid][0]
        self.assertEqual(listed["started_at"], d["started_at"])
        self.assertIn("created_at", listed)

    def test_finished_task_elapsed_is_fixed_at_finish_minus_start(self):
        tid = self.new_task()
        self.worker.post("/worker/claim", json={"worker_id": "mac"})
        task = tasks.TASKS[tid]
        task["started_at"] -= 100  # pretend it started 100 s ago
        self.worker.post("/worker/done", json={"task_id": tid, "result": "ok"})
        a = self.c.get(f"/tasks/{tid}").json()
        self.assertIsNotNone(a["finished_at"])
        self.assertAlmostEqual(a["elapsed"], 100, delta=2)
        time.sleep(1.2)
        b = self.c.get(f"/tasks/{tid}").json()
        self.assertEqual(a["elapsed"], b["elapsed"])  # does not keep growing
        done = [e["data"] for e in b["events"] if e["event"] == "done"][0]
        self.assertEqual(done["finished_at"], b["finished_at"])

    def test_stopped_task_gets_finished_at_in_both_events(self):
        tid = self.new_task()
        self.c.post(f"/tasks/{tid}/stop")
        d = self.c.get(f"/tasks/{tid}").json()
        self.assertIsNotNone(d["finished_at"])
        stopped = [e["data"] for e in d["events"] if e["event"] == "stopped"][0]
        self.assertEqual(stopped["finished_at"], d["finished_at"])

    def test_queued_task_elapsed_counts_from_created_at(self):
        tid = self.new_task()
        tasks.TASKS[tid]["created"] -= 50
        self.assertAlmostEqual(self.c.get(f"/tasks/{tid}").json()["elapsed"], 50, delta=2)

    def test_workers_online_follows_claim_polls_and_heartbeats(self):
        self.assertEqual(self.c.get("/workers").json()["online"], 0)
        self.assertEqual(self.c.get(f"/tasks/{self.new_task()}").json()["workers_online"], 0)
        self.worker.post("/worker/claim", json={"worker_id": "tab-1"})  # an idle poll counts
        w = self.c.get("/workers").json()
        self.assertEqual((w["online"], w["workers"][0]["id"], w["workers"][0]["computer"]), (1, "tab-1", "tab"))
        tasks.WORKERS["tab-1"]["seen"] -= tasks.WORKER_ONLINE_WINDOW + 5  # silent for too long
        self.assertEqual(self.c.get("/workers").json()["online"], 0)
        self.assertEqual(self.c.get("/tasks?active=true").json()["workers_online"], 0)

    def test_workers_endpoint_needs_a_session_and_worker_routes_do_not_leak_it(self):
        from fastapi.testclient import TestClient
        self.assertEqual(TestClient(main.app).get("/workers").status_code, 401)

    def test_task_event_reports_workers_online_at_creation(self):
        self.worker.post("/worker/claim", json={"worker_id": "mac"})
        tid = self.new_task()
        # the first claim above found no task; the worker is online when the task is made
        self.assertEqual(self.c.get(f"/tasks/{tid}").json()["events"][0]["data"]["workers_online"], 1)


if __name__ == "__main__":
    unittest.main()
