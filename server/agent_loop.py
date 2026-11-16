"""Planner for the worker's loop: given what happened so far, choose the NEXT action (one at a time).

The worker runs the action, sends back the (clipped) output, and asks again, until the model says "done" or the step
limit is reached. Everything the model sees comes from the worker's history, so the final summary is written after the
real outputs were seen. The worker's allowed commands are repeated in the prompt (the server is deployed without
the worker code); keep them in sync with worker/haru_worker.py.
"""
import json
import os
import re
import shlex

MAX_STEPS = 15
HISTORY_STEPS = 12  # older steps are dropped from the prompt (the worker keeps all of them)
HISTORY_CHARS = 5000
FIELD_CHARS = 1200
ACTIONS = ("command", "answer", "done")

RULES = """You are the planner of an agent that works by running shell commands in a task workspace, one action at a time.
Reply with ONLY one JSON object (no prose, no code fences). Choose exactly one action:
{"action":"command","command":"<one shell command>","label":"<short Korean name of this step>"}
{"action":"answer","text":"<Korean text you write yourself from the outputs you have seen: explanation, summary, plan>"}
{"action":"done","summary":"<Korean final summary of what was actually done and found>"}
Always include "progress": <how many checklist items are finished so far, an integer>.
On the very first step also include "todos": [3 to 6 short Korean checklist strings].
Rules:
- Take as many steps as needed, but be efficient. Read files before you change them. After a command, look at its real output.
- Use "done" only after you have seen the outputs you rely on. The summary must be based on them. Never invent output.
- In "answer" and "summary" write ONLY what appears in the real command outputs shown below (and in the task text). Anything that is
  not in those outputs must not be written: no guessed file contents, names, numbers, or results. If you could not find something, say so.
  (실제 명령 출력에 있는 내용만 쓰고, 없는 건 쓰지 마라.)
- Use real line breaks in "answer" and "summary" (one point per line, e.g. three lines for "summarize in three lines"); never write the two characters \\n.
- Give ONE answer at most. After you have answered, the only next action is "done".
- Commands run with the workspace as the current folder. Use relative paths only: no absolute paths, no "~", no "..", no .env or secret files.
- Allowed commands: ls head cat pwd find (no -delete) grep wc sort sleep echo; git status/diff/log/show/add/commit; mkdir touch cp mv tee.
  Programs such as python or node, and anything else, run only in allow_all mode (isolated computers).
- Never delete, send data outside, push, deploy, or pay.
- If a step was SKIPPED (blocked) or FAILED, the reason is shown below. Do not finish the task because of it: choose a different way
  (another command, a smaller step, fixed quoting, a relative path) or explain it honestly with "answer"/"done" if there is no way.
- A command that was blocked twice must not be proposed again."""

MODE_HINTS = {
    "plan": "Mode is PLAN: no command will be executed. Write the plan as the \"done\" summary (or \"answer\" first).",
    "skip": "Mode is SKIP: only already-allowed read actions run; anything else is skipped.",
}


def clip(text, limit=FIELD_CHARS):
    """Head and tail of a long text, so the model sees both the beginning and the end."""
    text = str(text or "")
    if len(text) <= limit:
        return text
    head = int(limit * 0.7)
    return text[:head] + f"\n…(중략, 총 {len(text)}자)…\n" + text[-(limit - head):]


def clean_history(history):
    out = []
    for item in history if isinstance(history, list) else []:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind") if item.get("kind") in ("command", "answer", "skipped", "error") else "command"
        out.append({"kind": kind, "label": clip(item.get("label"), 120), "command": clip(item.get("command"), 600),
                    "output": clip(item.get("output")), "reason": clip(item.get("reason"), 400),
                    "exit_code": item.get("exit_code") if isinstance(item.get("exit_code"), int) else None,
                    "text": clip(item.get("text"))})
    return out


def blocked_counts(history):
    counts = {}
    for h in history:
        if h["kind"] == "skipped" and h["command"]:
            counts[h["command"]] = counts.get(h["command"], 0) + 1
    return counts


def format_history(history):
    lines = []
    total = len(history)
    shown = history[-HISTORY_STEPS:]
    for i, h in enumerate(shown, total - len(shown) + 1):
        if h["kind"] == "skipped":
            lines.append(f"Step {i} SKIPPED: $ {h['command']}\n  reason: {h['reason']}")
        elif h["kind"] == "error":
            code = f" exit {h['exit_code']}" if h["exit_code"] is not None else ""
            lines.append(f"Step {i} FAILED{code}: $ {h['command']}\n  output: {h['output']}" + (f"\n  reason: {h['reason']}" if h["reason"] else ""))
        elif h["kind"] == "answer":
            lines.append(f"Step {i} ANSWER you wrote: {h['text']}")
        else:
            lines.append(f"Step {i} OK: $ {h['command']}\n  output: {h['output']}")
    text = "\n".join(lines)
    head = f"(earlier {total - len(shown)} steps omitted)\n" if total > len(shown) else ""
    if len(text) > HISTORY_CHARS:  # keep the newest part; the marker lines stay
        text = "(older text cut)\n" + text[-HISTORY_CHARS:]
    return head + text


def build_prompt(task, body, extra=""):
    history = clean_history(body.get("history"))
    step = len(history) + 1
    content = body.get("content") if isinstance(body.get("content"), str) and body.get("content").strip() else task["content"]
    force = body.get("force_done") is True
    parts = [RULES, MODE_HINTS.get(task.get("mode"), ""),
             f"Task: {content}",
             f"Workspace entries: {json.dumps(body.get('entries', []), ensure_ascii=False)}",
             f"Step {step} of at most {MAX_STEPS}. " + ("This is the LAST step: reply with action \"done\" and summarize honestly what was done, what failed or was blocked, and what remains." if force else ""),
             "What happened so far:\n" + (format_history(history) or "(nothing yet: this is the first step; include todos)")]
    counts = blocked_counts(history)
    if any(h["kind"] == "answer" and h["text"].strip() for h in history):
        parts.append("You already answered (이미 답했다). Do NOT answer again: reply with action \"done\" only. "
                     "Its summary may restate the answer, with line breaks, using only what the real outputs showed.")
    twice = [c for c, n in counts.items() if n >= 2]
    if twice:
        parts.append("These commands were blocked twice and MUST NOT be proposed again: " + json.dumps(twice, ensure_ascii=False))
    if extra:
        parts.append(extra)
    return "\n\n".join(p for p in parts if p), history, counts


SECRET_RE = re.compile(r"gsk_[A-Za-z0-9]{8,}|nvapi-[A-Za-z0-9_-]{8,}|github_pat_[A-Za-z0-9_]{8,}|AIza[A-Za-z0-9_-]{8,}"
                       r"|\b\d{8,10}:[A-Za-z0-9_-]{30,}|Bearer\s+[A-Za-z0-9._~+/=-]{8,}|\b[A-Fa-f0-9]{40,}\b")
SECRET_ENV = ("GROQ_API_KEY", "NVIDIA_API_KEY", "GITHUB_TOKEN", "SESSION_SECRET", "SETUP_TOKEN", "WORKER_TOKEN",
              "HARU_BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "TELEGRAM_WEBHOOK_SECRET", "HARU_DEV_TOKEN")


def mask_secrets(text):
    """Anything that looks like a key or token, and the values of the server's own secrets, never reach the log."""
    text = str(text or "")
    for name in SECRET_ENV:
        value = os.environ.get(name, "")
        if len(value) >= 6:
            text = text.replace(value, "***")
    return SECRET_RE.sub("***", text)


def json_objects(text):
    """Every top-level JSON object in a reply, in order (text before/after, code fences, examples are skipped)."""
    decoder = json.JSONDecoder(strict=False)  # a raw line break inside a string is accepted and kept
    i = 0
    while True:
        i = text.find("{", i)
        if i < 0:
            return
        try:
            obj, end = decoder.raw_decode(text, i)
        except ValueError:
            i += 1
            continue
        if isinstance(obj, dict):
            yield obj
            i = end
        else:
            i += 1


def extract_json(text):
    """The first JSON object in the reply (kept for callers that only need an object)."""
    return next(json_objects(text or ""), None)


WORDS = {
    "command": "command", "cmd": "command", "run": "command", "shell": "command", "bash": "command", "exec": "command",
    "execute": "command", "tool": "command", "run_command": "command", "shell_command": "command",
    "answer": "answer", "reply": "answer", "respond": "answer", "response": "answer", "say": "answer",
    "explain": "answer", "message": "answer", "text": "answer",
    "done": "done", "finish": "done", "finished": "done", "final": "done", "complete": "done", "completed": "done",
    "end": "done", "stop": "done", "finalize": "done", "final_answer": "done", "summary": "done",
}
WRAPPERS = ("next_action", "next", "action_request", "response", "result", "data", "output")


def _lower(d):
    return {str(k).lower(): v for k, v in d.items()}


def _first(d, *names):
    for n in names:
        if d.get(n) not in (None, ""):
            return d[n]
    return None


def _as_command(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value and all(isinstance(x, (str, int, float)) and not isinstance(x, bool) for x in value):
        return shlex.join(str(x) for x in value)  # an argv array: ["ls", "-la"]
    return None


def normalize(obj, depth=0):
    """Common variants of the reply shape -> {"action", ...} (or None): keys in any case, "type"/"action"/"kind" names,
    wrappers like {"next_action": {...}} or {"actions": [{...}]}, a command given as an array."""
    if not isinstance(obj, dict) or depth > 3:
        return None
    d = _lower(obj)
    if isinstance(d.get("actions"), list) and d["actions"] and isinstance(d["actions"][0], dict):
        return normalize(d["actions"][0], depth + 1)
    if isinstance(d.get("action"), dict):
        d = {**d, **_lower(d["action"])}
        d.pop("action", None)
    name = None
    for key in ("action", "type", "kind", "name", "act", "tool"):
        v = d.get(key)
        if isinstance(v, str):
            name = WORDS.get(v.strip().lower().replace(" ", "_").replace("-", "_"))
            if name:
                break
    command = _as_command(_first(d, "command", "cmd", "shell_command", "shell", "bash", "argv", "args"))
    if name is None:
        for key in WRAPPERS:
            if isinstance(d.get(key), dict):
                inner = normalize(d[key], depth + 1)
                if inner:
                    return {**{k: v for k, v in d.items() if k in ("progress", "todos")}, **inner}
        name = "command" if command else "done" if _first(d, "summary") else "answer" if _first(d, "text", "answer", "reply") else None
    out = {"progress": d.get("progress"), "todos": d.get("todos")}
    if name == "command":
        return {**out, "action": "command", "command": command, "label": _first(d, "label", "title", "description", "name") if isinstance(_first(d, "label", "title", "description", "name"), str) else ""}
    if name == "answer":
        return {**out, "action": "answer", "text": _first(d, "text", "answer", "reply", "response", "message", "content")}
    if name == "done":
        return {**out, "action": "done", "summary": _first(d, "summary", "result", "final", "final_answer", "text", "message", "answer", "content")}
    return None


def fix_newlines(text):
    """Models sometimes write the two characters backslash+n instead of a line break: turn them into real line breaks
    (only when the text has no real line break yet and does not look like a Windows path such as C:\\new)."""
    if "\n" not in text and "\\n" in text and not re.search(r"[A-Za-z]:\\", text):
        text = text.replace("\\r\\n", "\n").replace("\\n", "\n")
    return text


def validate(action):
    """A clean action dict or None."""
    if not isinstance(action, dict) or action.get("action") not in ACTIONS:
        return None
    kind = action["action"]
    if kind == "command":
        cmd = action.get("command")
        if not isinstance(cmd, str) or not cmd.strip() or len(cmd) > 1500:
            return None
        return {"action": "command", "command": cmd.strip(), "label": str(action.get("label") or "")[:100]}
    key = "text" if kind == "answer" else "summary"
    text = action.get(key)
    if not isinstance(text, str) or not text.strip():
        return None
    return {"action": kind, key: fix_newlines(text.strip())[:4000]}


def parse_reply(text):
    """(clean action, raw normalized dict) from the first object in the reply that is a usable action, else (None, {})."""
    for obj in json_objects(text or ""):
        raw = normalize(obj)
        clean = validate(raw)
        if clean:
            return clean, raw
    return None, {}


def update_todos(task, action, first_step):
    """Keeps task["todos"] in step with the model: new list on the first step, `progress` items done afterwards."""
    todos = action.get("todos")
    if first_step and isinstance(todos, list) and 3 <= len(todos) <= 6 and all(isinstance(t, str) and t.strip() for t in todos):
        task["todos"] = [{"id": f"t{i + 1}", "text": t.strip()[:120], "done": False} for i, t in enumerate(todos)]
    items = task.get("todos") or []
    progress = action.get("progress")
    done_count = len(items) if action.get("action") == "done" else (progress if isinstance(progress, int) and not isinstance(progress, bool) else None)
    if done_count is not None:
        done_count = max(0, min(done_count, len(items)))
        items = [{**t, "done": i < done_count or t.get("done", False)} for i, t in enumerate(items)]
        task["todos"] = items
    return items


REMINDER = ("Your last reply could not be used. Reply with ONLY one JSON object and nothing else: no explanation, no code fences. "
            "(JSON 객체 하나로만 답해.)")


async def next_action(ask, task, body, trace=None, nvidia_modes=()):
    """`ask(messages, mode)` -> (text, model). Returns (action | None, model, todos).
    A reply that cannot be read is asked again once in the same conversation; if that fails too, Groq is skipped and the
    NVIDIA models are asked. `trace` (a dict) collects why it failed, for the log. A command that was blocked twice and
    is proposed again gets one re-ask, then an honest "done"."""
    trace = trace if trace is not None else {}
    trace.setdefault("reasons", [])
    prompt, history, counts = build_prompt(task, body)
    base = [{"role": "user", "content": prompt}]

    async def attempt(label, messages, mode="easy"):
        text, model = await ask(messages, mode)
        text = text or ""
        trace.update(model=model, head=text[:300], saw_text=trace.get("saw_text", False) or bool(text.strip()))
        clean, raw = parse_reply(text)
        if clean is None:
            trace["reasons"].append(f"{label}: " + ("빈 답" if not text.strip() else "형식 오류"))
        return clean, raw, text, model

    action, raw, text, model = await attempt("1차", base)
    if action is None:
        again = base + [{"role": "assistant", "content": text or "(empty)"}, {"role": "user", "content": REMINDER}]
        action, raw, text, model = await attempt("재시도", again)
        for nv in list(nvidia_modes)[:2]:
            if action is not None:
                break
            action, raw, text, model = await attempt(f"NVIDIA({nv.split('/')[-1]})", again, nv)  # Groq is skipped
    if action is None:
        return None, model, task.get("todos") or []

    if action["action"] == "command" and counts.get(action["command"], 0) >= 2:
        note = (f"You proposed {json.dumps(action['command'], ensure_ascii=False)} again but it was blocked twice. "
                "Choose a DIFFERENT approach now (another command, or explain with answer/done).")
        retry, retry_raw, _t, model = await attempt("차단 반복", base + [{"role": "assistant", "content": text}, {"role": "user", "content": note}])
        if retry is None or (retry["action"] == "command" and counts.get(retry["command"], 0) >= 2):
            action = {"action": "done", "summary": "같은 명령이 계속 막혀서 다른 방법을 찾지 못했습니다. 막힌 명령: " + action["command"]}
            raw = {}
        else:
            action, raw = retry, retry_raw
    if action["action"] == "answer" and any(h["kind"] == "answer" and h["text"].strip() for h in history):
        action = {"action": "done", "summary": action["text"]}  # answered twice: the last answer is the final summary
    if body.get("force_done") is True and action["action"] != "done":
        action = {"action": "done", "summary": action.get("text") or action.get("summary") or "단계 제한에 도달해 멈췄습니다."}
    todos = update_todos(task, {**raw, **action}, first_step=not history)
    return action, model, todos
