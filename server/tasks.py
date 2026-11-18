"""In-memory task queue shared by the web API and authenticated workers."""
import asyncio
import os
import secrets
import time
import uuid
from collections import deque

TASKS = {}
EVENTS = {}
LOCK = asyncio.Lock()
HEARTBEAT_TIMEOUT = 120
PERMISSION_MODES = {"always_ask", "auto_edit", "plan", "auto", "skip", "allow_all"}
STALE_RUNNING = 300  # a running task with no sign of its worker for 5 minutes is failed ("일꾼 응답 없음")
STALE_QUEUED = 600  # a task nobody took for 10 minutes is failed ("일할 컴퓨터가 받지 않음")
WORKERS = {}  # worker_id -> {"seen": epoch of the last claim poll or heartbeat, "computer": ...}
WORKER_ONLINE_WINDOW = 60  # idle workers poll /worker/claim every 10 s; running ones send a heartbeat every 30 s


def computer_of(worker_id):
    w = str(worker_id).lower()
    return "actions" if "action" in w else "codespaces" if "codespace" in w else "tab" if "tab" in w or "termux" in w else "mac"


def touch_worker(worker_id, now=None):
    WORKERS[str(worker_id)] = {"seen": now or time.time(), "computer": computer_of(worker_id)}


def workers_online(now=None):
    """Workers seen recently (claim poll or heartbeat). Empty list = nothing can run a queued task."""
    now = now or time.time()
    return [{"id": wid, "computer": w["computer"], "last_seen": w["seen"]}
            for wid, w in WORKERS.items() if now - w["seen"] <= WORKER_ONLINE_WINDOW]


def timing(task, now=None):
    """Clock facts of a task, all UTC epoch seconds, so every device shows the same elapsed time.
    `started_at` is when a worker took it (None while queued); the elapsed time counts from it, or from `created_at`
    while the task is still queued. A finished task is fixed at finished_at - start."""
    now = now or time.time()
    begin = task.get("started_at") or task["created"]
    end = task.get("finished_at") or now
    return {"created_at": task["created"], "started_at": task.get("started_at"),
            "finished_at": task.get("finished_at"), "now": now, "elapsed": max(0, int(end - begin))}


def touch_task(task, now=None):
    """The worker showed a sign of life for this task (event, poll, permission request, model call)."""
    task["worker_seen"] = now or time.time()


def fail_task(task, reason):
    """Ends a task nobody is working on: status failed, a `failed` event with the reason (the screens show it)."""
    task.update(status="failed", rewind_only=False, pending_permission=None)
    mark_finished(task)
    add_event(task["id"], "status", {"status": "failed", "computer": task["computer"], **timing(task)})
    add_event(task["id"], "failed", {"result": "", "error": reason, "finished_at": task["finished_at"]})


def sweep(now=None):
    """Fails stuck tasks: running with no heartbeat or worker event for STALE_RUNNING seconds, or queued for more
    than STALE_QUEUED seconds. Returns [(task_id, reason)]. Safe to call again and again."""
    now = now or time.time()
    changed = []
    for task in list(TASKS.values()):
        if task["status"] == "running":
            last = max(task.get("heartbeat") or 0, task.get("worker_seen") or 0)
            if now - last > STALE_RUNNING:
                fail_task(task, "일꾼 응답 없음")
                changed.append((task["id"], "일꾼 응답 없음"))
        elif task["status"] == "queued":
            if now - (task.get("queued_at") or task["created"]) > STALE_QUEUED:
                fail_task(task, "일할 컴퓨터가 받지 않음")
                changed.append((task["id"], "일할 컴퓨터가 받지 않음"))
    return changed


def mark_finished(task):
    task["finished_at"] = time.time()
    return task["finished_at"]


def add_event(task_id, kind, data):
    event = {"id": len(EVENTS[task_id]) + 1, "event": kind, "data": data, "time": time.time()}
    EVENTS[task_id].append(event)
    return event


def publish(task_id, kind, data):
    if task_id not in TASKS:
        return None
    return add_event(task_id, kind, data)


def action_event(task_id, command, label, status="running", **extra):
    task = TASKS[task_id]
    action_id = task.get("action_id") or uuid.uuid4().hex
    task["action_id"] = action_id
    add_event(task_id, "action", {"id": action_id, "label": label, "command": command,
                                  "status": status, "outward": False, **extra})
    return action_id


def worker_authorized(token):
    expected = os.environ.get("WORKER_TOKEN", "")
    return bool(expected and secrets.compare_digest(token or "", expected))


async def create(content, mode, conversation_id):
    if mode not in PERMISSION_MODES:
        raise ValueError("invalid permission mode")
    task_id = secrets.token_hex(12)
    async with LOCK:
        TASKS[task_id] = {"id": task_id, "content": content, "mode": mode,
                          "conversation_id": conversation_id, "status": "queued",
                          "created": time.time(), "worker": None, "heartbeat": 0,
                          "checkpoint": None, "messages": deque(), "permissions": deque(),
                          "controls": deque(),
                          "todos": [{"id": "t1", "text": content, "done": False}],
                          "rewind_only": False,
                          "steps": [], "pending_permission": None, "resume_after": 0,
                          "computer": None, "started_at": None, "finished_at": None, "action_id": None,
                          "queued_at": time.time(), "worker_seen": 0}
        EVENTS[task_id] = []
        add_event(task_id, "task", {"id": task_id, "content": content, "mode": mode,
                                    "conversation_id": conversation_id, "chatId": conversation_id,
                                    "chat_mode": "work", "status": "queued",
                                    "created_at": TASKS[task_id]["created"], "now": time.time(),
                                    "workers_online": len(workers_online())})
        add_event(task_id, "todos", {"todos": [{"id": "t1", "text": content, "done": False}]})
    return TASKS[task_id]


async def claim(worker_id):
    async with LOCK:
        now = time.time()
        touch_worker(worker_id, now)  # an idle worker is "connected" as long as it keeps polling here
        for task in TASKS.values():
            stale = task["status"] == "running" and now - task["heartbeat"] > HEARTBEAT_TIMEOUT
            if task["status"] == "queued" or stale:
                task.update(status="running", worker=worker_id, heartbeat=now, worker_seen=now)
                task["computer"] = computer_of(worker_id)
                task["started_at"] = task["started_at"] or now
                task["finished_at"] = None  # running again (first run, retry after a lost worker, or a rewind)
                task["resume_after"] = task["checkpoint"].get("step", -1) + 1 if task["checkpoint"] else 0
                add_event(task["id"], "status", {"status": "running", "worker": worker_id,
                                                    "computer": task["computer"], "started_at": task["started_at"],
                                                    "created_at": task["created"], "now": now,
                                                    "elapsed": int(now - task["started_at"]),
                                                    "resume_after": task["resume_after"]})
                return {k: task[k] for k in ("id", "content", "mode", "conversation_id", "checkpoint", "resume_after", "rewind_only")}
    return None


async def heartbeat(task_id, worker_id, checkpoint=None):
    async with LOCK:
        task = TASKS.get(task_id)
        if not task or task["worker"] != worker_id or task["status"] != "running":
            return False
        task["heartbeat"] = time.time()
        task["worker_seen"] = task["heartbeat"]
        touch_worker(worker_id, task["heartbeat"])
        if checkpoint is not None:
            task["checkpoint"] = checkpoint
            add_event(task_id, "checkpoint", checkpoint)
        return True


def record_action(task_id, action, output, summary):
    task = TASKS[task_id]
    step = len(task["steps"])
    item = {"step": step, "action": action, "output": output, "summary": summary}
    task["steps"].append(item)
    add_event(task_id, "action", {"step": step, "command": action})
    add_event(task_id, "output", {"step": step, "text": output})
    add_event(task_id, "summary", {"step": step, "text": summary})
    return step
