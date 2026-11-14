"""Planner for the worker's loop: given what happened so far, choose the NEXT action (one at a time).

The worker runs the action, sends back the (clipped) output, and asks again, until the model says "done" or the step
limit is reached. Everything the model sees comes from the worker's history, so the final summary is written after the
real outputs were seen. The worker's allowed commands are repeated in the prompt (the server is deployed without
the worker code); keep them in sync with worker/haru_worker.py.
"""
import json
import re

MAX_STEPS = 15
HISTORY_STEPS = 12  # older steps are dropped from the prompt (the worker keeps all of them)
HISTORY_CHARS = 7000
FIELD_CHARS = 1500
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
    head = int(limit * 0.6)
    return text[:head] + "\n…(중략)…\n" + text[-(limit - head):]


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
    twice = [c for c, n in counts.items() if n >= 2]
    if twice:
        parts.append("These commands were blocked twice and MUST NOT be proposed again: " + json.dumps(twice, ensure_ascii=False))
    if extra:
        parts.append(extra)
    return "\n\n".join(p for p in parts if p), history, counts


def extract_json(text):
    """The first JSON object in the reply (models sometimes add fences or a sentence)."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?", "", t).strip()
    t = re.sub(r"```$", "", t).strip()
    try:
        value = json.loads(t)
        return value if isinstance(value, dict) else None
    except ValueError:
        pass
    start = t.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(t)):
            depth += (t[i] == "{") - (t[i] == "}")
            if depth == 0:
                try:
                    value = json.loads(t[start:i + 1])
                    if isinstance(value, dict):
                        return value
                except ValueError:
                    pass
                break
        start = t.find("{", start + 1)
    return None


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
    return {"action": kind, key: text.strip()[:4000]}


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


async def next_action(ask, task, body):
    """`ask(prompt)` -> (text, model). Returns (action dict | None, model, todos). One retry when the reply is not a valid
    action, and one re-ask when the model repeats a command that was already blocked twice."""
    prompt, history, counts = build_prompt(task, body)
    text, model = await ask(prompt)
    action = validate(extract_json(text or ""))
    if action is None:
        text, model = await ask(prompt + "\n\nYour last reply was not a valid JSON action. Reply with ONLY one JSON object.")
        action = validate(extract_json(text or ""))
    raw = extract_json(text or "") or {}
    if action and action["action"] == "command" and counts.get(action["command"], 0) >= 2:
        text, model = await ask(prompt + f"\n\nYou proposed {json.dumps(action['command'], ensure_ascii=False)} again but it was blocked twice. "
                                          "Choose a DIFFERENT approach now (another command, or explain with answer/done).")
        retry = validate(extract_json(text or ""))
        raw = extract_json(text or "") or {}
        if retry is None or (retry["action"] == "command" and counts.get(retry["command"], 0) >= 2):
            action = {"action": "done", "summary": "같은 명령이 계속 막혀서 다른 방법을 찾지 못했습니다. 막힌 명령: " + action["command"]}
            raw = {}
        else:
            action = retry
    if action is None:
        return None, model, task.get("todos") or []
    if body.get("force_done") is True and action["action"] != "done":
        action = {"action": "done", "summary": action.get("text") or action.get("summary") or "단계 제한에 도달해 멈췄습니다."}
    todos = update_todos(task, {**raw, **action}, first_step=not history)
    return action, model, todos
