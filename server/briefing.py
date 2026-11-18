"""Morning briefing: Haru speaks first. Every minute the server checks whether it is past BRIEF_HOUR (KST, default 8)
and today's briefing was not sent yet; then one Telegram message goes to TELEGRAM_CHAT_ID. The date of the last
briefing is stored with the normal store so a restart never sends it twice. "/brief" in Telegram sends one right now."""
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone

import moment
import notify
import storage

log = logging.getLogger("uvicorn.error")
KST = timezone(timedelta(hours=9))
STATE_PATH = ".agent/briefing/state.json"
INTERVAL = 60
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


async def compose(now=None) -> str:
    """The morning text: the same as the "wake" moment; with nothing to say, a plain greeting."""
    text, _ = await moment.say("wake", now)
    return text or "좋은 아침이에요. 오늘도 필요한 게 있으면 말씀해 주세요."


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
