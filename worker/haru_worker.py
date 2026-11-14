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
READ_COMMANDS = {"ls", "head", "cat", "pwd", "find", "grep", "wc", "sort", "sleep", "echo"}
EDIT_COMMANDS = {"mkdir", "touch", "cp", "mv", "tee"}
ALLOWED_TEXT = "ls head cat pwd find grep wc sort sleep echo, git status/diff/log/show/add/commit, mkdir touch cp mv tee"
MAX_STEPS = 15  # model decisions per task (command, answer, blocked and failed steps all count)
COMMAND_TIMEOUT = int(os.environ.get("HARU_COMMAND_TIMEOUT", "120"))
OUTPUT_FOR_MODEL = 1500  # characters of one output sent back to the model (the server clips again)
# "allow_all" runs without asking, so it is honored only on isolated computers (Actions, Codespaces)
ISOLATED = os.environ.get("HARU_ISOLATED") == "1" or any(w in WORKER_ID.lower() for w in ("action", "codespace"))


class Restart(Exception):
    """A rewind was applied while a step ran: start the task over from the rewound state."""


def api(path, body=None, method="POST", timeout=30):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method,
        headers={"X-Worker-Token": TOKEN, "Content-Type": "application/json", "User-Agent": "haru-worker/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
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


def apply_messages(task, messages):
    for message in messages:
        task["content"] += "\n\n추가 요청: " + message["content"]
        publish(task["id"], "interjection_applied", {"id": message["id"], "status": "queued_for_next_action"})


def block_reason(command):
    """Why the static safety rules refuse this command (a sentence the model can act on), or None when it is allowed."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return "따옴표가 맞지 않아 명령을 해석할 수 없습니다. 따옴표를 짝 맞춰서 다시 쓰세요"
    if DENIED_PATH.search(command):
        return ".env 파일 접근은 항상 차단됩니다"
    hit = BLOCKED.search(command)
    if hit:
        return f"차단된 명령입니다 ({hit.group(0).strip()}): 삭제, 외부 전송, push, 배포, 결제는 하지 않습니다"
    if any(".." in token for token in tokens):
        return "상위 폴더(..)는 쓸 수 없습니다. 작업 폴더 안의 상대경로만 쓰세요"
    if any(token.startswith(("/", "~")) or re.search(r"=(?:/|~)", token) for token in tokens[1:]):
        return "절대경로(/ 또는 ~)는 쓸 수 없습니다. 작업 폴더 안의 상대경로만 쓰세요"
    return None


def safe_command(command):
    return block_reason(command) is None


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


def check(task, command, action_id, label):
    """(allowed, reason). The reason is what the model is told and what the skipped event shows."""
    mode = task["mode"]
    why = block_reason(command)
    if why:
        return False, why  # always, in every mode (BLOCKED commands and .env)
    classification = command_class(command)
    if mode == "allow_all":
        if ISOLATED:
            return True, ""  # no permission asked; only the safety rules above apply
        return False, "전부 허용 모드는 격리된 컴퓨터(GitHub Actions, Codespaces)에서만 실행됩니다"
    if mode == "plan":
        return False, "계획 모드에서는 명령을 실행하지 않습니다"
    if classification == "unknown":
        try:
            first = (shlex.split(re.split(r"&&|\|\||[|;]", command)[0])[:1] or ["?"])[0]
        except ValueError:
            first = "?"
        return False, f"허용 목록 밖 명령입니다 ({first}). 허용: {ALLOWED_TEXT}"
    if mode == "skip":
        return False, "묻지 않음 모드에서는 미리 허락하지 않은 행동을 건너뜁니다"
    if mode == "auto_edit" and classification in ("read", "edit"):
        return True, ""
    if mode == "auto" and classification == "read":
        return True, ""
    decision = api("/worker/permission", {"task_id": task["id"], "action_id": action_id,
                                           "label": label, "command": command}).get("decision")
    if decision in ("allow", "always"):
        return True, ""
    return False, "허락하지 않았거나 허락을 받지 못했습니다"


def permission(task, command, action_id, label):
    return check(task, command, action_id, label)[0]


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


def clip(text, limit=OUTPUT_FOR_MODEL):
    text = str(text or "")
    if len(text) <= limit:
        return text
    head = int(limit * 0.6)
    return text[:head] + "\n…(중략)…\n" + text[-(limit - head):]


def poll(task, work):
    """Between steps (and while a command runs): stop, rewind and extra requests from the user."""
    state = api("/worker/events?task_id=" + task["id"], method="GET")
    task["mode"] = state.get("mode", task["mode"])
    if state.get("stopped"):
        raise RuntimeError("task stopped")
    if state.get("controls"):
        apply_controls(task, state["controls"], work)
        raise Restart()
    apply_messages(task, state.get("messages", []))


def run_command(task, work, command):
    """Runs one command in the workspace. Returns (output, returncode). While it runs, checks for stop / rewind /
    extra requests once a second; a command that ends sooner returns right away."""
    process = subprocess.Popen(command, cwd=work, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    started = last_poll = time.time()
    while True:
        try:
            output, _ = process.communicate(timeout=0.2)
            return (output or "")[-20000:], process.returncode
        except subprocess.TimeoutExpired:
            pass
        now = time.time()
        if now - last_poll >= 1:
            last_poll = now
            try:
                poll(task, work)
            except BaseException:
                process.terminate()
                process.communicate()
                raise
        if now - started > COMMAND_TIMEOUT:
            process.terminate()
            output, _ = process.communicate()
            return (output or "")[-20000:] + f"\n(시간 초과: {COMMAND_TIMEOUT}초 안에 끝나지 않아 멈췄습니다)", 124


def git(work, *args, check=True):
    return subprocess.run(["git", "-c", "user.name=Haru Worker", "-c", "user.email=worker@localhost", *args], cwd=work, check=check,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)


def changed_files(work, baseline):
    """Files that differ from the state at the start of the task: [{path, change}]."""
    try:
        git(work, "add", "-A")
        out = git(work, "diff", "--name-status", baseline, "--cached").stdout
        names = {"A": "added", "M": "modified", "D": "deleted"}
        files = []
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0][:1] in names:
                files.append({"path": parts[-1], "change": names[parts[0][:1]]})
        return files[:50]
    except Exception:
        return []


def run_task(task):
    """The loop: ask the model for the next action, run it, send back the output, repeat until it says "done"
    (or MAX_STEPS). A blocked or failed step is reported to the model, never the end of the task."""
    if task["mode"] not in MODES:
        raise ValueError("unsupported permission mode")
    task["_restarts"] = task.get("_restarts", 0) + 1
    if task["_restarts"] > 5:
        raise RuntimeError("too many rewinds")
    work = ROOT / task["id"]
    seed_workspace(work)
    (work / ".git").exists() or subprocess.run(["git", "init", "-q", str(work)], check=True)
    exclude = work / ".git" / "info" / "exclude"
    existing = exclude.read_text() if exclude.exists() else ""
    if ".env" not in existing:
        exclude.write_text(existing + "\n.env\n.env.*\nnode_modules/\n")
    initial_state = api("/worker/events?task_id=" + task["id"], method="GET")
    task["mode"] = initial_state.get("mode", task["mode"])
    if initial_state.get("stopped"):
        raise RuntimeError("task stopped")
    apply_messages(task, initial_state.get("messages", []))
    if initial_state.get("controls"):
        apply_controls(task, initial_state["controls"], work)
    if task.get("rewind_only") or initial_state.get("rewind_only"):
        if not initial_state.get("controls"):
            raise RuntimeError("rewind request is missing")
        return "마지막 체크포인트로 되돌렸습니다."
    if DENIED_PATH.search(task["content"]):
        action_id = secrets.token_hex(8)
        publish(task["id"], "action", {"id": action_id, "label": "요청 보안 검사", "command": "요청 검증", "status": "running", "outward": False})
        publish(task["id"], "skipped", {"id": action_id, "command": "요청 검증", "reason": ".env 접근 요청은 항상 차단됩니다"})
        return "건너뜀: .env 접근은 차단되었습니다."

    # the starting state, to list the changed files at the end
    try:
        if git(work, "rev-parse", "--verify", "-q", "HEAD", check=False).returncode != 0:
            git(work, "add", "-A")
            git(work, "commit", "--allow-empty", "-m", "baseline")
        baseline = git(work, "rev-parse", "HEAD").stdout.strip()
    except Exception:
        baseline = ""

    history, blocked, skipped_list = [], {}, []
    checkpoint = task.get("checkpoint") or {}
    if checkpoint.get("command"):  # taken over from a worker that was lost: tell the model what it did last
        history.append({"kind": "command", "label": "이전 일꾼이 실행한 마지막 명령", "command": checkpoint["command"],
                        "output": clip(checkpoint.get("output", ""))})
    n_checkpoints = int(checkpoint.get("step", -1)) + 1 if checkpoint else 0
    try:
        while True:
            poll(task, work)
            entries = [p.name for p in work.iterdir() if p.name not in (".git", ".env") and not p.name.startswith(".env.")]
            force = len(history) >= MAX_STEPS
            resp = api("/worker/next", {"task_id": task["id"], "content": task["content"], "entries": entries,
                                         "history": history, "force_done": force}, timeout=180)
            if resp.get("todos"):
                publish(task["id"], "todos", {"todos": resp["todos"]})
            kind = resp.get("action")
            if kind == "done" or force:
                summary = str(resp.get("summary") or resp.get("text") or "작업을 마쳤습니다.")
                if force:
                    summary = f"※ 최대 {MAX_STEPS}단계에 도달해 중간에 멈췄습니다. " + summary
                break
            action_id = secrets.token_hex(8)
            if kind == "answer":
                text = str(resp.get("text") or "")
                publish(task["id"], "action", {"id": action_id, "label": "답변 정리", "command": "(모델이 글로 답함)", "status": "running", "outward": False, "model": resp.get("model")})
                publish(task["id"], "action", {"id": action_id, "label": "답변 정리", "command": "(모델이 글로 답함)", "status": "done", "outward": False})
                publish(task["id"], "output", {"id": action_id, "command": "(모델이 글로 답함)", "text": text, "is_diff": False})
                history.append({"kind": "answer", "text": text})
                continue
            if kind != "command" or not resp.get("command"):
                raise RuntimeError("model returned an invalid action")
            command = resp["command"]
            label = resp.get("label") or ("명령 실행: " + command[:72])
            publish(task["id"], "action", {"id": action_id, "label": label, "command": command, "status": "running", "outward": False, "model": resp.get("model")})
            if blocked.get(command, 0) >= 2:
                allowed, reason = False, "같은 명령이 이미 2번 막혔습니다. 다른 방법을 쓰세요"
            else:
                allowed, reason = check(task, command, action_id, label)
            if not allowed:
                blocked[command] = blocked.get(command, 0) + 1
                publish(task["id"], "skipped", {"id": action_id, "command": command, "reason": reason})
                print(f"[{task['id'][:8]}] 건너뜀: {command[:100]!r} -> {reason}", flush=True)
                skipped_list.append({"text": command, "reason": reason})
                history.append({"kind": "skipped", "label": label, "command": command, "reason": reason + (" (같은 명령이 2번 막혔습니다: 반드시 다른 방법을 쓰세요)" if blocked[command] >= 2 else "")})
                continue
            api("/worker/heartbeat", {"task_id": task["id"], "worker_id": WORKER_ID,
                                       "checkpoint": {"action_id": action_id, "step": n_checkpoints - 1, "command": command, "output": ""}})
            output, code = run_command(task, work, command)
            if code:
                publish(task["id"], "error", {"id": action_id, "command": command, "reason": "command failed", "exit_code": code, "output": output})
                print(f"[{task['id'][:8]}] 실패({code}): {command[:100]!r}", flush=True)
                history.append({"kind": "error", "label": label, "command": command, "output": clip(output), "exit_code": code, "reason": "명령이 실패했습니다"})
                continue
            git(work, "add", "-A")
            git(work, "commit", "--allow-empty", "-m", "checkpoint")
            checkpoint = {"action_id": action_id, "step": n_checkpoints, "command": command, "output": output,
                          "commit": git(work, "rev-parse", "HEAD").stdout.strip()}
            n_checkpoints += 1
            task["checkpoint"] = checkpoint
            api("/worker/heartbeat", {"task_id": task["id"], "worker_id": WORKER_ID, "checkpoint": checkpoint})
            publish(task["id"], "action", {"id": action_id, "label": label, "command": command, "status": "done", "outward": False, "checkpoint": True})
            publish(task["id"], "output", {"id": action_id, "command": command, "text": output,
                                              "is_diff": bool(re.search(r"(?:^|\n)(?:diff --git |@@ )", output))})
            history.append({"kind": "command", "label": label, "command": command, "output": clip(output)})
    except Restart:
        return run_task(task)
    publish(task["id"], "summary", {"text": summary, "files": changed_files(work, baseline) if baseline else [], "skipped": skipped_list, "usage": []})
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
        except (OSError, urllib.error.URLError) as exc:
            print(f"서버 연결 실패: {exc}", flush=True)
            time.sleep(10)


if __name__ == "__main__":
    main()
