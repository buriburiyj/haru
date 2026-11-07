"""In-memory task queue shared by the web API and authenticated workers."""
import asyncio
import os
import secrets
import time
from collections import deque

TASKS = {}
EVENTS = {}
LOCK = asyncio.Lock()
HEARTBEAT_TIMEOUT = 120
PERMISSION_MODES = {"always_ask", "auto_edit", "plan", "auto", "skip", "allow_all"}


def add_event(task_id, kind, data):
    event = {"id": len(EVENTS[task_id]) + 1, "event": kind, "data": data, "time": time.time()}
    EVENTS[task_id].append(event)
    return event


def publish(task_id, kind, data):
    if task_id not in TASKS:
        return None
    return add_event(task_id, kind, data)


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
                          "steps": [], "pending_permission": None, "resume_after": 0}
        EVENTS[task_id] = []
        add_event(task_id, "task", {"id": task_id, "content": content, "mode": mode,
                                    "conversation_id": conversation_id, "status": "queued"})
    return TASKS[task_id]


async def claim(worker_id):
    async with LOCK:
        now = time.time()
        for task in TASKS.values():
            stale = task["status"] == "running" and now - task["heartbeat"] > HEARTBEAT_TIMEOUT
            if task["status"] == "queued" or stale:
                task.update(status="running", worker=worker_id, heartbeat=now)
                task["resume_after"] = task["checkpoint"].get("step", -1) + 1 if task["checkpoint"] else 0
                add_event(task["id"], "status", {"status": "running", "worker": worker_id,
                                                    "resume_after": task["resume_after"]})
                return {k: task[k] for k in ("id", "content", "mode", "conversation_id", "checkpoint", "resume_after")}
    return None


async def heartbeat(task_id, worker_id, checkpoint=None):
    async with LOCK:
        task = TASKS.get(task_id)
        if not task or task["worker"] != worker_id or task["status"] != "running":
            return False
        task["heartbeat"] = time.time()
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
