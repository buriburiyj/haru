"""Polling Termux worker. It never listens on a port and keeps API keys on the server."""
import json
import os
import pathlib
import re
import shlex
import shutil
import secrets
import subprocess
import threading
import time
import urllib.error
import urllib.request

BASE = os.environ.get("HARU_SERVER_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.environ["WORKER_TOKEN"]
WORKER_ID = os.environ.get("WORKER_ID", "tab")
ROOT = pathlib.Path(os.environ.get("HARU_WORK_DIR", str(pathlib.Path.home() / "haru-work")))
SOURCE = pathlib.Path(os.environ.get("HARU_SOURCE_DIR", os.getcwd())).resolve()
MODES = {"always_ask", "auto_edit", "plan", "auto", "skip", "allow_all"}
BLOCKED = re.compile(r"\b(?:rm|rmdir|shred|unlink|truncate|mkfs|dd|curl|wget|scp|sftp|rsync|nc|ncat|socat|pay|purchase|checkout)\b|git\s+(?:push|remote)|\b(?:deploy|sendmail|mail)\b|\s>\s*[/~]|\bfind\b[^\n]*-delete", re.I)
DENIED_PATH = re.compile(r"(?:^|[\s/'\"])(?:\.env(?:\.[^\s/'\"]*)?|[^\s/'\"]*/\.env(?:\.[^\s/'\"]*)?|~/computer-use/\.env)(?:$|[\s/'\"])", re.I)
READ_COMMANDS = {"ls", "head", "cat", "pwd", "find", "grep", "wc", "sort", "sleep"}
EDIT_COMMANDS = {"mkdir", "touch", "cp", "mv", "tee"}


def api(path, body=None, method="POST"):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method,
        headers={"X-Worker-Token": TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def publish(task_id, kind, data):
    api("/worker/event", {"task_id": task_id, "event": kind, "data": data})


def apply_controls(task, controls, work):
    for control in controls:
        if control.get("kind") != "rewind":
            continue
        commit = control.get("checkpoint", {}).get("commit", "")
        if not re.fullmatch(r"[0-9a-f]{40,64}", commit):
            raise RuntimeError("invalid rewind checkpoint")
        subprocess.run(["git", "reset", "--hard", commit], cwd=work, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        task["checkpoint"] = control["checkpoint"]
        publish(task["id"], "rewound", {"id": control.get("action_id"), "checkpoint": commit})


def safe_command(command):
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    if DENIED_PATH.search(command) or BLOCKED.search(command) or any(".." in token for token in tokens):
        return False
    if any(token.startswith(("/", "~")) or re.search(r"=(?:/|~)", token) for token in tokens[1:]):
        return False
    return True


def mutating_command(command):
    return bool(re.search(r"(?:>>?|\btee\b|\bsed\s+-i\b|\bmv\b|\bcp\b|\bmkdir\b|\btouch\b|\bpython\b|\bnode\b|\bgit\s+(?:add|commit)\b)", command, re.I))


def command_class(command):
    segments = re.split(r"&&|\|\||[|;]", command)
    try:
        commands = [shlex.split(segment) for segment in segments]
    except ValueError:
        return "unknown"
    names = [(parts[0].rsplit("/", 1)[-1], parts[1] if len(parts) > 1 else "") for parts in commands if parts]
    if names and all(name in READ_COMMANDS or (name == "git" and sub in {"status", "diff", "log", "show"}) for name, sub in names):
        return "read"
    if names and all(name in READ_COMMANDS | EDIT_COMMANDS or (name == "git" and sub in {"add", "commit"}) for name, sub in names) and any(name in EDIT_COMMANDS or (name == "git" and sub in {"add", "commit"}) for name, sub in names):
        return "edit"
    return "unknown"


def permission(task, command, action_id, label):
    mode = task["mode"]
    if not safe_command(command) or command_class(command) == "unknown" or mode in ("plan", "skip", "allow_all"):
        return False
    classification = command_class(command)
    if mode == "auto_edit" and classification in ("read", "edit"):
        return True
    if mode == "auto" and classification == "read":
        return True
    if mode == "auto":
        decision = api("/worker/permission", {"task_id": task["id"], "action_id": action_id,
                                               "label": label, "command": command}).get("decision")
        return decision in ("allow", "always")
    decision = api("/worker/permission", {"task_id": task["id"], "action_id": action_id,
                                           "label": label, "command": command}).get("decision")
    return decision in ("allow", "always")


def seed_workspace(work):
    if work.exists() and any(work.iterdir()):
        return
    work.mkdir(parents=True, exist_ok=True)
    if SOURCE != work.resolve() and SOURCE.is_dir():
        ignored = shutil.ignore_patterns(".git", ".env", ".env.*", "node_modules", "dist", "build", "__pycache__", ".venv")
        for item in SOURCE.iterdir():
            if item.name in {".git", ".env"} or item.name.startswith(".env."):
                continue
            target = work / item.name
            if item.is_dir():
                shutil.copytree(item, target, ignore=ignored, dirs_exist_ok=True)
            elif item.is_file() and item.stat().st_size <= 50 * 1024 * 1024:
                shutil.copy2(item, target)


def run_task(task):
    if task["mode"] not in MODES:
        raise ValueError("unsupported permission mode")
    work = ROOT / task["id"]
    seed_workspace(work)
    (work / ".git").exists() or subprocess.run(["git", "init", "-q", str(work)], check=True)
    exclude = work / ".git" / "info" / "exclude"
    existing = exclude.read_text() if exclude.exists() else ""
    if ".env" not in existing:
        exclude.write_text(existing + "\n.env\n.env.*\nnode_modules/\n")
    entries = [p.name for p in work.iterdir() if p.name not in (".git", ".env") and not p.name.startswith(".env.")]
    if DENIED_PATH.search(task["content"]):
        action_id = secrets.token_hex(8)
        publish(task["id"], "action", {"id": action_id, "label": "요청 보안 검사", "command": "요청 검증", "status": "running", "outward": False})
        publish(task["id"], "skipped", {"id": action_id, "command": "요청 검증", "reason": ".env 접근 요청은 항상 차단됩니다"})
        return "건너뜀: .env 접근은 차단되었습니다."
    plan = api("/worker/plan", {"task_id": task["id"], "entries": entries})
    command, summary = plan["command"], plan["summary"]
    label = plan.get("label") or ("명령 실행: " + command[:72])
    initial_state = api("/worker/events?task_id=" + task["id"], method="GET")
    task["mode"] = initial_state.get("mode", task["mode"])
    if initial_state.get("stopped"):
        raise RuntimeError("task stopped")
    if initial_state.get("controls"):
        apply_controls(task, initial_state["controls"], work)
        return run_task(task)
    task_queue_checkpoint = task.get("checkpoint") or {}
    action_id = (task_queue_checkpoint.get("action_id")
                 if task.get("_action_count", 0) == 0 and task_queue_checkpoint.get("command") == command
                 else None) or secrets.token_hex(8)
    publish(task["id"], "action", {"id": action_id, "label": label, "command": command,
                                    "status": "running", "outward": False})
    if not permission(task, command, action_id, label):
        publish(task["id"], "skipped", {"id": action_id, "command": command, "reason": "실행 허락을 받지 못했거나 안전 정책으로 건너뛰었습니다"})
        return "건너뜀: 실행 허락을 받지 못했습니다."
    task["_action_count"] = task.get("_action_count", 0) + 1
    if task["_action_count"] > 10:
        raise RuntimeError("action limit reached")
    interjected = False
    if task_queue_checkpoint.get("command") == command and task_queue_checkpoint.get("output"):
        output = task_queue_checkpoint["output"]
    else:
        api("/worker/heartbeat", {"task_id": task["id"], "worker_id": WORKER_ID,
             "checkpoint": {"action_id": action_id, "step": -1, "command": command, "output": ""}})
        publish(task["id"], "action", {"id": action_id, "label": label, "command": command,
                                         "status": "running", "outward": False, "model": plan.get("model")})
        process = subprocess.Popen(command, cwd=work, shell=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        while process.poll() is None:
            time.sleep(1)
            state = api("/worker/events?task_id=" + task["id"], method="GET")
            task["mode"] = state.get("mode", task["mode"])
            if state.get("stopped"):
                process.terminate()
                raise RuntimeError("task stopped")
            if state.get("controls"):
                process.terminate()
                process.communicate()
                apply_controls(task, state["controls"], work)
                return run_task(task)
            for message in state.get("messages", []):
                task["content"] += "\n\n추가 요청: " + message["content"]
                publish(task["id"], "interjection_applied", {"id": message["id"], "status": "queued_for_next_action"})
                interjected = True
        output, _ = process.communicate()
        output = output[-20000:]
        if process.returncode:
            publish(task["id"], "error", {"id": action_id, "command": command, "reason": "command failed", "exit_code": process.returncode, "output": output})
            raise RuntimeError("command failed")
        subprocess.run(["git", "add", "-A"], cwd=work, check=True)
        subprocess.run(["git", "-c", "user.name=Haru Worker", "-c", "user.email=worker@localhost",
            "commit", "--allow-empty", "-m", "checkpoint"], cwd=work,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        checkpoint = {"action_id": action_id, "step": 0, "command": command, "output": output,
                      "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=work, text=True).strip()}
        task["checkpoint"] = checkpoint
        api("/worker/heartbeat", {"task_id": task["id"], "worker_id": WORKER_ID, "checkpoint": checkpoint})
    publish(task["id"], "action", {"id": action_id, "label": label, "command": command,
                                     "status": "done", "outward": False,
                                     "checkpoint": bool(task.get("checkpoint"))})
    publish(task["id"], "output", {"id": action_id, "command": command, "text": output,
                                      "is_diff": bool(re.search(r"(?:^|\n)(?:diff --git |@@ )", output))})
    if interjected:
        return run_task(task)
    publish(task["id"], "summary", {"text": summary, "files": [], "skipped": [], "usage": []})
    return summary


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            task = api("/worker/claim", {"worker_id": WORKER_ID}).get("task")
            if task:
                stop_heartbeat = threading.Event()
                def heartbeat_loop():
                    while not stop_heartbeat.wait(30):
                        try:
                            api("/worker/heartbeat", {"task_id": task["id"], "worker_id": WORKER_ID,
                                                       "checkpoint": task.get("checkpoint")})
                        except Exception:
                            pass
                heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
                heartbeat_thread.start()
                try:
                    result = run_task(task)
                    api("/worker/done", {"task_id": task["id"], "result": result})
                except Exception as exc:
                    api("/worker/done", {"task_id": task["id"], "error": str(exc)})
                finally:
                    stop_heartbeat.set()
                    heartbeat_thread.join(timeout=1)
            else:
                time.sleep(5)
        except (OSError, urllib.error.URLError):
            time.sleep(10)


if __name__ == "__main__":
    main()
