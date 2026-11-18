"""Morning briefing: Haru speaks first. Every minute the server checks whether it is past BRIEF_HOUR (KST, default 8)
and today's briefing was not sent yet; then one Telegram message goes to TELEGRAM_CHAT_ID. The date of the last
briefing is stored with the normal store so a restart never sends it twice. "/brief" in Telegram sends one right now."""
import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone

import eye
import notify
import search
import storage
import tasks

log = logging.getLogger("uvicorn.error")
KST = timezone(timedelta(hours=9))
STATE_PATH = ".agent/briefing/state.json"
INTERVAL = 60
MAX_LINES = 5
SYSTEM = ("너는 '하루'다. 아침에 먼저 말을 거는 다정한 브리핑을 한국어로 써라. 5줄 이내, 한 줄에 한 가지, 존댓말(해요체). "
          "마크다운·목록 기호·링크·이모지 없이. 아래 재료에 있는 내용만 쓰고, 재료가 없는 항목은 아예 쓰지 마라. "
          "첫 줄은 짧은 아침 인사와 날씨.")

_last_sent = None  # "YYYY-MM-DD" of the last briefing; None = not read from the store yet
_lock = asyncio.Lock()


def brief_hour() -> int:
    try:
        return min(23, max(0, int(os.environ.get("BRIEF_HOUR", "8"))))
    except ValueError:
        return 8


def is_due(now: datetime, last) -> bool:
    kst = now.astimezone(KST)
    return kst.hour >= brief_hour() and last != kst.strftime("%Y-%m-%d")


async def _read_last():
    text = await storage.read_file(STATE_PATH)
    return json.loads(text).get("last") if text else ""


async def _write_last(day: str):
    await storage.commit_file(STATE_PATH, json.dumps({"last": day}), "briefing: sent " + day, "briefing-state")


def work_lines(now: datetime) -> list:
    """Finished and failed Work tasks since the start of yesterday (KST): one line each, newest first."""
    since = (now.astimezone(KST).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)).timestamp()
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


async def gather(now: datetime) -> dict:
    """The raw material; every part may be empty."""
    weather = []
    try:
        for r in (await search.search("서울 날씨 오늘"))[:3]:
            weather.append(f"{r.get('title', '')}: {r.get('snippet', '')}"[:200])
    except Exception as exc:
        log.warning("briefing weather failed: %s", type(exc).__name__)
    seen = []
    try:
        for e in await eye.recent(2):
            seen.append(f"하루 눈이 본 것: {e.get('scene', '')} (질문 \"{e.get('question', '')}\")"[:200])
    except Exception as exc:
        log.warning("briefing eye log failed: %s", type(exc).__name__)
    return {"weather": weather, "work": work_lines(now), "eye": seen}


def tidy(text: str) -> str:
    """Plain lines: no markdown, links or bullets; at most MAX_LINES."""
    text = re.sub(r"\[([^\]]*)\]\(https?://[^)]*\)", r"\1", text or "")
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_`#>]+", "", text)
    lines = [re.sub(r"^\s*(?:[-•]|\d+[.)])\s+", "", ln).strip() for ln in text.splitlines()]
    return "\n".join([ln for ln in lines if ln][:MAX_LINES])


def fallback(material: dict) -> str:
    lines = ["좋은 아침이에요."]
    if material["weather"]:
        lines.append("서울 날씨: " + material["weather"][0].split(": ", 1)[-1])
    lines += material["work"][:2] + material["eye"][:1]
    return tidy("\n".join(lines))


async def compose(now=None) -> str:
    now = now or datetime.now(timezone.utc)
    material = await gather(now)
    parts = [("서울 날씨(검색 결과)", material["weather"]), ("어제~오늘 Work 작업", material["work"]), ("하루 눈 최근 기록", material["eye"])]
    body = "\n\n".join(f"[{name}]\n" + "\n".join(items) for name, items in parts if items)
    if not body:
        return "좋은 아침이에요. 오늘도 필요한 게 있으면 말씀해 주세요."
    try:
        text, _ = await eye.llm([{"role": "system", "content": SYSTEM},
                                 {"role": "user", "content": f"오늘은 {now.astimezone(KST).strftime('%Y-%m-%d')}이에요.\n\n{body}"}])
        text = tidy(text)
    except Exception as exc:
        log.warning("briefing model failed: %s", type(exc).__name__)
        text = ""
    return text or fallback(material)


async def deliver(send=None, now=None) -> bool:
    """Writes a briefing and sends it to TELEGRAM_CHAT_ID. Does not touch the "sent today" date."""
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not chat:
        return False
    send = send or notify._http_send
    text = await compose(now)
    return bool(await send("sendMessage", {"chat_id": chat, "text": text, "disable_web_page_preview": True}))


async def tick(now=None, send=None) -> bool:
    """One check: sends the briefing if it is due. True when one was sent."""
    global _last_sent
    now = now or datetime.now(timezone.utc)
    async with _lock:
        if not os.environ.get("TELEGRAM_CHAT_ID"):
            return False
        if _last_sent is None:
            try:
                _last_sent = await _read_last() or ""
            except Exception as exc:  # cannot tell whether it was sent: do not risk a second one
                log.warning("briefing state unreadable: %s", type(exc).__name__)
                return False
        if not is_due(now, _last_sent):
            return False
        day = now.astimezone(KST).strftime("%Y-%m-%d")
        if not await deliver(send, now):
            return False  # asked again next minute
        _last_sent = day
        await _write_last(day)
        log.info("briefing sent for %s", day)
        return True


async def loop(interval: int = INTERVAL):
    while True:
        try:
            await tick()
        except Exception as exc:
            log.warning("briefing tick failed: %s", type(exc).__name__)
        await asyncio.sleep(interval)
