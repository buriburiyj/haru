"""Polling Termux worker. It never listens on a port and keeps API keys on the server."""
import json
import os
import pathlib
import re
import subprocess
import time
import urllib.error
import urllib.request

BASE = os.environ.get("HARU_SERVER_URL", "http://localhost:8000").rstrip("/")
TOKEN = os.environ["WORKER_TOKEN"]
WORKER_ID = os.environ.get("WORKER_ID", "tab")
ROOT = pathlib.Path.home() / "haru-work"
MODES = {"default", "acceptEdits", "plan", "auto", "bypassPermissions", "dontAsk"}
BLOCKED = re.compile(r"(^|[;&|\s])(?:rm|rmdir|shred)\b|\b(?:curl|wget|scp|sftp|rsync)\b|\b(?:pay|purchase|checkout)\b", re.I)


def api(path, body=None, method="POST"):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method,
        headers={"X-Worker-Token": TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def run_task(task):
    if task["mode"] not in MODES:
        raise ValueError("unsupported permission mode")
    work = ROOT / task["id"]
    work.mkdir(parents=True, exist_ok=True)
    (work / ".git").exists() or subprocess.run(["git", "init", "-q", str(work)], check=True)
    prompt = task["content"].strip()
    if re.search(r"(?:\.env|/\.env|\.env\b)", prompt, re.I):
        raise PermissionError(".env access is blocked")
    if BLOCKED.search(prompt):
        raise PermissionError("destructive, outbound, and payment actions require explicit handling")
    # Command execution is deliberately opt-in via a fenced command block.
    commands = re.findall(r"```(?:sh|bash)\s*\n(.*?)```", prompt, re.S)
    if not commands:
        raise RuntimeError("No executable shell command was provided")
    output = []
    for command in commands:
        if BLOCKED.search(command) or re.search(r"\.env", command, re.I):
            raise PermissionError("blocked command")
        result = subprocess.run(command, cwd=work, shell=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
        output.append(result.stdout[-20000:])
        subprocess.run(["git", "add", "-A"], cwd=work, check=True)
        subprocess.run(["git", "-c", "user.name=Haru Worker", "-c", "user.email=worker@localhost",
            "commit", "--allow-empty", "-m", "checkpoint"], cwd=work,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        api("/worker/heartbeat", {"task_id": task["id"], "worker_id": WORKER_ID,
             "checkpoint": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=work, text=True).strip()})
        if result.returncode:
            raise RuntimeError("command failed: " + result.stdout[-4000:])
    return "\n".join(output)


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
