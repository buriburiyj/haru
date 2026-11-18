"""Moments: what the phone automation sends ("wake", "leave", "home", "charge") and one short spoken answer.
Material is collected with a time limit, the fast model writes 2-3 plain Korean sentences (next model if one fails,
a short default sentence if all fail), nothing to say -> silence, and each event speaks once a day (kept in the store).
The morning Telegram briefing uses the same code as "wake"."""
import asyncio
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone

import eye
import router
import search
import tasks

log = logging.getLogger("uvicorn.error")
KST = timezone(timedelta(hours=9))
EVENTS = ("wake", "leave", "home", "charge")
STATE_PATH = ".agent/moment/state.json"
GATHER_TIMEOUT = 2.5   # each kind of material
BUDGET = 4.5           # whole answer; the phone waits 5 s at most
MAX_LINES = 5
DEFAULTS = {"wake": "좋은 아침이에요.", "leave": "조심히 다녀오세요.", "home": "어서 오세요.", "charge": "충전을 시작했어요."}
GOALS = {
    "wake": "방금 일어난 사용자에게 날씨와 오늘 할 일, 어제 Work 작업 결과를 알려 주는 아침 인사",
    "leave": "집을 나서는 사용자에게 비가 오는지(검색 결과에 비·소나기가 있을 때만)와 끝난 작업을 알려 주는 한마디",
    "home": "집에 돌아온 사용자에게 오늘 끝나거나 실패한 작업, 남은 할 일을 알려 주는 한마디",
    "charge": "충전을 시작한 사용자에게 오늘 한 일을 간단히 요약해 주는 한마디",
}
SYSTEM = ("너는 '하루'다. {goal}을(를) 소리로 읽기 좋은 한국어 2~3문장(해요체)으로 말해라. "
          "마크다운·목록 기호·링크·이모지 없이. 아래 재료에 있는 내용만 쓰고, 재료가 없는 항목은 말하지 마라.")

_said = {}  # "YYYY-MM-DD" -> set of events already spoken; mirrors the store
_loaded = False
_lock = asyncio.Lock()


def day_of(now: datetime) -> str:
    return now.astimezone(KST).strftime("%Y-%m-%d")


def midnight(now: datetime, days_back: int = 0) -> float:
    return (now.astimezone(KST).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=days_back)).timestamp()


def work_lines(now: datetime, days_back: int = 1) -> list:
    """Finished and failed Work tasks since the start of `days_back` days ago (KST): one line each, newest first."""
    since = midnight(now, days_back)
    done, failed = [], []
    for t in sorted(tasks.TASKS.values(), key=lambda x: x.get("finished_at") or 0, reverse=True):
        if not t.get("finished_at") or t["finished_at"] < since:
            continue
        title = " ".join(str(t.get("content", "")).split())[:40]
        if t["status"] == "done":
            done.append(f"끝난 작업: {title}")
        elif t["status"] == "failed":
            error = ""
            for e in reversed(tasks.EVENTS.get(t["id"], [])):
                if e["event"] == "failed":
                    error = str(e["data"].get("error", ""))[:40]
                    break
            failed.append(f"실패한 작업: {title}" + (f" ({error})" if error else ""))
    return done[:2] + failed[:2]


def todo_lines() -> list:
    """Work tasks still waiting or running: today's to-do list."""
    open_tasks = [t for t in tasks.TASKS.values() if t["status"] in ("queued", "running")]
    return [f"할 일: {' '.join(str(t.get('content', '')).split())[:40]}" for t in open_tasks[:3]]


async def weather(query: str = "서울 날씨 오늘") -> list:
    return [f"{r.get('title', '')}: {r.get('snippet', '')}"[:200] for r in (await search.search(query))[:3]]


async def eye_lines(now: datetime, today_only: bool = False, limit: int = 2) -> list:
    out = []
    for e in await eye.recent(20 if today_only else limit):
        if today_only and float(e.get("time", 0)) < midnight(now):
            continue
        out.append(f"하루 눈이 본 것: {e.get('scene', '')} (질문 \"{e.get('question', '')}\")"[:200])
    return out[:limit]


async def _part(name: str, coro) -> list:
    try:
        return await asyncio.wait_for(coro, GATHER_TIMEOUT)
    except Exception as exc:  # a slow or broken source is simply left out
        log.warning("moment %s skipped: %s", name, type(exc).__name__)
        return []


async def gather(event: str, now: datetime, data=None) -> list:
    """[(title, [lines])] for the event; empty lists are dropped."""
    async def now_list(items):
        return items

    if event == "wake":
        spec = [("서울 날씨(검색 결과)", weather()), ("오늘 할 일", now_list(todo_lines())),
                ("어제~오늘 Work 작업", now_list(work_lines(now, 1))), ("하루 눈 최근 기록", eye_lines(now))]
    elif event == "leave":
        spec = [("비 여부(검색 결과)", weather("서울 비 오늘 강수")), ("끝난 작업", now_list(work_lines(now, 0)))]
    elif event == "home":
        spec = [("오늘 작업", now_list(work_lines(now, 0))), ("남은 할 일", now_list(todo_lines()))]
    else:
        battery = data.get("battery") if isinstance(data, dict) else None
        extra = [f"배터리 {int(battery)}%"] if isinstance(battery, (int, float)) and not isinstance(battery, bool) and 0 <= battery <= 100 else []
        spec = [("오늘 한 일", now_list(work_lines(now, 0))), ("오늘 하루 눈 기록", eye_lines(now, True, 3)), ("충전 정보", now_list(extra))]
    results = await asyncio.gather(*[_part(name, c) for name, c in spec])
    return [(name, lines) for (name, _), lines in zip(spec, results) if lines]


def tidy(text: str) -> str:
    """Plain lines: no markdown, links or bullets; at most MAX_LINES."""
    text = re.sub(r"\[([^\]]*)\]\(https?://[^)]*\)", r"\1", text or "")
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_`#>]+", "", text)
    lines = [re.sub(r"^\s*(?:[-•]|\d+[.)])\s+", "", ln).strip() for ln in text.splitlines()]
    return "\n".join([ln for ln in lines if ln][:MAX_LINES])


def fallback(event: str, material: list) -> str:
    """Short plain text when no model answered: the default sentence, plus the first weather or work line for wake."""
    lines = [DEFAULTS[event]]
    if event == "wake":
        for name, items in material:
            if name.startswith("서울 날씨"):
                lines.append("서울 날씨: " + items[0].split(": ", 1)[-1])
        lines += [items[0] for name, items in material if name.startswith(("오늘 할 일", "어제"))]
    return tidy("\n".join(lines))


async def write(event: str, now: datetime, material: list, deadline: float) -> str:
    """The fast model first, then the NVIDIA models one by one, all inside the deadline. "" when none answered."""
    body = "\n\n".join(f"[{name}]\n" + "\n".join(items) for name, items in material)
    messages = [{"role": "system", "content": SYSTEM.format(goal=GOALS[event])},
                {"role": "user", "content": f"오늘은 {day_of(now)}이에요.\n\n{body}"}]
    for mode in ["easy"] + router.NVIDIA_MODELS[:2]:
        left = deadline - time.monotonic()
        if left < 0.3:
            break
        try:
            text, _ = await asyncio.wait_for(eye.llm(messages, mode), left)
            text = tidy(text)
            if text:
                return text
        except Exception as exc:
            log.warning("moment model %s failed: %s", mode, type(exc).__name__)
    return ""


async def say(event: str, now=None, data=None, budget=None) -> tuple:
    """-> (text, had_material). text is "" only when there was nothing to say."""
    now = now or datetime.now(timezone.utc)
    deadline = time.monotonic() + (BUDGET if budget is None else budget)
    material = await gather(event, now, data)
    if not material:
        return "", False
    return (await write(event, now, material, deadline)) or fallback(event, material), True


async def _load_state():
    global _loaded
    if _loaded:
        return
    import storage
    try:
        text = await storage.read_file(STATE_PATH)
        for day, events in (json.loads(text) if text else {}).items():
            _said[day] = set(events)
    except Exception as exc:  # unreadable store: keep going with this process's memory
        log.warning("moment state unreadable: %s", type(exc).__name__)
        return
    _loaded = True


async def _save_state(day: str):
    import storage
    for old in [d for d in _said if d != day]:
        del _said[old]
    await storage.commit_file(STATE_PATH, json.dumps({d: sorted(v) for d, v in _said.items()}), "moment: " + day, "moment-state")


async def moment(event: str, data=None, now=None) -> str:
    """The answer for one phone event: "" (silence) when already spoken today or nothing to say."""
    now = now or datetime.now(timezone.utc)
    day = day_of(now)
    async with _lock:
        await _load_state()
        if event in _said.get(day, set()):
            return ""
        text, had = await say(event, now, data)
        if not had:
            return ""
        _said.setdefault(day, set()).add(event)
        try:
            await _save_state(day)
        except Exception as exc:
            log.warning("moment state not saved: %s", type(exc).__name__)
        log.info("moment %s spoken", event)
        return text
