"""Polling Termux worker. It never listens on a port and keeps API keys on the server."""
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
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


def permission(task, command):
    mode = task["mode"]
    if not safe_command(command):
        publish(task["id"], "skipped", {"command": command, "reason": "항상 중지 대상 또는 .env 접근"})
        return False
    if command_class(command) == "unknown":
        publish(task["id"], "skipped", {"command": command, "reason": "분류되지 않은 명령은 안전상 실행하지 않습니다"})
        return False
    if mode == "plan":
        publish(task["id"], "skipped", {"command": command, "reason": "계획 모드는 실행하지 않습니다"})
        return False
    if mode == "skip":
        publish(task["id"], "skipped", {"command": command, "reason": "묻지 않음 모드: 사전 허락이 없어 건너뜀"})
        return False
    classification = command_class(command)
    if mode == "auto_edit" and classification in ("read", "edit"):
        return True
    if mode == "auto" and classification == "read":
        return True
    if mode == "auto":
        decision = api("/worker/permission", {"task_id": task["id"], "command": command}).get("decision")
        return decision in ("allow", "always")
    if mode == "allow_all":  # Local workers are never treated as Actions/Codespaces.
        publish(task["id"], "skipped", {"command": command, "reason": "전부 허용은 Actions/Codespaces에서만 가능"})
        return False
    decision = api("/worker/permission", {"task_id": task["id"], "command": command}).get("decision")
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
        publish(task["id"], "skipped", {"reason": ".env 접근 요청은 항상 차단됩니다"})
        return "건너뜀: .env 접근은 차단되었습니다."
    plan = api("/worker/plan", {"task_id": task["id"], "entries": entries})
    command, summary = plan["command"], plan["summary"]
    if not permission(task, command):
        return "건너뜀: 실행 허락을 받지 못했습니다."
    task_queue_checkpoint = task.get("checkpoint") or {}
    if task_queue_checkpoint.get("command") == command and task_queue_checkpoint.get("output"):
        output = task_queue_checkpoint["output"]
    else:
        api("/worker/heartbeat", {"task_id": task["id"], "worker_id": WORKER_ID,
             "checkpoint": {"step": -1, "command": command, "output": ""}})
        publish(task["id"], "action", {"command": command, "model": plan.get("model")})
        process = subprocess.Popen(command, cwd=work, shell=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        last_heartbeat = 0.0
        while process.poll() is None:
            time.sleep(1)
            state = api("/worker/events?task_id=" + task["id"], method="GET")
            if state.get("stopped"):
                process.terminate()
                raise RuntimeError("task stopped")
            if time.monotonic() - last_heartbeat >= 30:
                api("/worker/heartbeat", {"task_id": task["id"], "worker_id": WORKER_ID,
                     "checkpoint": {"step": -1, "command": command}})
                last_heartbeat = time.monotonic()
        output, _ = process.communicate()
        output = output[-20000:]
        if process.returncode:
            publish(task["id"], "error", {"reason": "command failed", "exit_code": process.returncode, "output": output})
            raise RuntimeError("command failed")
        subprocess.run(["git", "add", "-A"], cwd=work, check=True)
        subprocess.run(["git", "-c", "user.name=Haru Worker", "-c", "user.email=worker@localhost",
            "commit", "--allow-empty", "-m", "checkpoint"], cwd=work,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        checkpoint = {"step": 0, "command": command, "output": output,
                      "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=work, text=True).strip()}
        api("/worker/heartbeat", {"task_id": task["id"], "worker_id": WORKER_ID, "checkpoint": checkpoint})
    publish(task["id"], "output", {"command": command, "text": output})
    publish(task["id"], "summary", {"text": summary, "files": []})
    return summary


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            task = api("/worker/claim", {"worker_id": WORKER_ID}).get("task")
            if task:
                try:
                    result = run_task(task)
                    api("/worker/done", {"task_id": task["id"], "result": result})
                except Exception as exc:
                    api("/worker/done", {"task_id": task["id"], "error": str(exc)})
            else:
                time.sleep(5)
        except (OSError, urllib.error.URLError):
            time.sleep(10)


if __name__ == "__main__":
    main()
