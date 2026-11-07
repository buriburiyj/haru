"""Telegram notifications for Haru tasks.

Uses the Haru bot (HARU_BOT_TOKEN) with sendMessage/answerCallbackQuery only.
Never calls getUpdates, so it cannot conflict with junbot.
"""
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger("haru.notify")

KST = timezone(timedelta(hours=9))
APP_URL = "https://buriburiyj.github.io/haru/"
API = "https://api.telegram.org/bot{token}/{method}"
RISKY_KINDS = {"delete", "send", "pay"}
QUIET_START, QUIET_END = 23, 8
BUTTON_TTL = 24 * 3600
MAX_PENDING = 30

TITLES = {
    "done": "작업을 마쳤습니다",
    "failed": "작업이 실패했습니다",
    "skipped": "건너뛴 단계가 있습니다",
    "permission": "허락이 필요합니다",
}


def is_quiet(now: datetime) -> bool:
    hour = now.astimezone(KST).hour
    return hour >= QUIET_START or hour < QUIET_END


async def _http_send(method: str, payload: dict) -> bool:
    token = os.environ.get("HARU_BOT_TOKEN", "")
    if not token:
        return False
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(API.format(token=token, method=method), json=payload)
        if r.status_code != 200:
            log.warning("telegram %s returned %s", method, r.status_code)
        return r.status_code == 200
    except Exception as exc:  # never log the URL: it contains the token
        log.warning("telegram %s failed: %s", method, type(exc).__name__)
        return False


class Notifier:
    def __init__(self, send=_http_send, now=None, queue_file=None, chat_id=None):
        self._send = send
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._chat_id = chat_id
        self._queue_file = Path(queue_file or os.environ.get("NOTIFY_QUEUE_FILE", "/tmp/haru-notify.json"))
        self._pending = self._load()
        self._buttons = {}  # token -> (task_id, request_id, decision, expires_at)

    @property
    def chat_id(self) -> str:
        if self._chat_id is not None:
            return str(self._chat_id)
        return os.environ.get("TELEGRAM_CHAT_ID", "")

    def _load(self) -> list:
        try:
            data = json.loads(self._queue_file.read_text())
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _save(self) -> None:
        try:
            self._queue_file.write_text(json.dumps(self._pending, ensure_ascii=False))
        except OSError as exc:
            log.warning("notify queue not saved: %s", type(exc).__name__)

    @staticmethod
    def _text(kind: str, title: str, detail: str = "") -> str:
        lines = [f"[하루] {TITLES.get(kind, kind)}", title.strip()[:200]]
        if detail:
            lines.append(detail.strip()[:500])
        lines.append(APP_URL)
        return "\n".join(line for line in lines if line)

    async def notify(self, kind: str, title: str, detail: str = "") -> bool:
        """done / failed / skipped. Batched during quiet hours (23-08 KST)."""
        if not self.chat_id:
            return False
        now = self._now()
        if is_quiet(now):
            self._pending.append({"kind": kind, "title": title.strip()[:80],
                                  "at": now.astimezone(KST).strftime("%H:%M")})
            self._pending = self._pending[-MAX_PENDING:]
            self._save()
            return True
        await self.flush()
        return await self._send("sendMessage", {"chat_id": self.chat_id,
                                                "text": self._text(kind, title, detail)})

    async def flush(self) -> bool:
        """Send the overnight digest once quiet hours are over."""
        if not self._pending or not self.chat_id or is_quiet(self._now()):
            return False
        lines = [f"[하루] 밤사이 알림 {len(self._pending)}개"]
        lines += [f"- {p['at']} {TITLES.get(p['kind'], p['kind'])}: {p['title']}" for p in self._pending]
        lines.append(APP_URL)
        ok = await self._send("sendMessage", {"chat_id": self.chat_id, "text": "\n".join(lines)})
        if ok:
            self._pending = []
            self._save()
        return ok

    def _prune(self) -> None:
        now = time.time()
        self._buttons = {k: v for k, v in self._buttons.items() if v[3] > now}

    async def ask_permission(self, task_id: str, request_id: str, title: str, kind: str = "other") -> bool:
        """Sent immediately (silently at night). Risky kinds get no 'always' button."""
        if not self.chat_id:
            return False
        self._prune()

        def button(label: str, decision: str) -> dict:
            token = secrets.token_urlsafe(6)
            self._buttons[token] = (task_id, request_id, decision, time.time() + BUTTON_TTL)
            return {"text": label, "callback_data": f"p:{token}"}

        row = [button("허락", "allow")]
        if kind not in RISKY_KINDS:
            row.append(button("항상 허락", "always"))
        row.append(button("거절", "deny"))
        return await self._send("sendMessage", {
            "chat_id": self.chat_id,
            "text": self._text("permission", title),
            "reply_markup": {"inline_keyboard": [row]},
            "disable_notification": is_quiet(self._now()),
        })

    def resolve_callback(self, update: dict):
        """Return (task_id, request_id, decision, callback_id) or None. One use per request."""
        cq = update.get("callback_query") or {}
        data = cq.get("data", "")
        chat = str(((cq.get("message") or {}).get("chat") or {}).get("id", ""))
        if not self.chat_id or chat != self.chat_id or not data.startswith("p:"):
            return None
        self._prune()
        hit = self._buttons.get(data[2:])
        if not hit:
            return None
        task_id, request_id, decision, _ = hit
        self._buttons = {k: v for k, v in self._buttons.items() if v[:2] != (task_id, request_id)}
        return task_id, request_id, decision, cq.get("id", "")

    async def answer(self, callback_id: str, text: str) -> bool:
        return await self._send("answerCallbackQuery", {"callback_query_id": callback_id, "text": text[:180]})


notifier = Notifier()


# --- task hooks (wired from main.py with notify.install(task_queue)) ---------
import asyncio as _asyncio

HOOK_KINDS = {"done", "failed", "skipped", "permission_required"}
DECISION_TEXT = {"allow": "허락했습니다", "always": "항상 허락했습니다", "deny": "거절했습니다"}
_background = set()
_skipped = {}
_depth = 0
_waiting = {}  # task_id -> request_id the task is waiting on


def _track(task_id, kind, data):
    data = data or {}
    if kind == "permission_required":
        _waiting[task_id] = str(data.get("id") or data.get("action_id") or "")
    elif kind in ("permission", "done", "failed", "stopped"):
        _waiting.pop(task_id, None)


def _task_title(task):
    task = task or {}
    return str(task.get("title") or task.get("content") or "작업")[:80]


async def _dispatch(task_id, task, kind, data, n=None):
    n = n or notifier
    try:
        if kind == "skipped":
            _skipped[task_id] = _skipped.get(task_id, 0) + 1
            return
        title = _task_title(task)
        if kind == "done":
            count = _skipped.pop(task_id, 0)
            await n.notify("done", title, f"건너뛴 단계 {count}개" if count else "")
        elif kind == "failed":
            _skipped.pop(task_id, None)
            await n.notify("failed", title, str(data.get("error") or data.get("reason") or "")[:300])
        elif kind == "permission_required":
            request_id = str(data.get("id") or data.get("action_id") or "")
            label = str(data.get("label") or data.get("title") or data.get("command") or title)
            await n.ask_permission(task_id, request_id, label, str(data.get("kind") or "other"))
    except Exception as exc:
        log.warning("notify hook failed: %s", type(exc).__name__)


def on_event(task_id, kind, data, tasks_map, n=None):
    """Sync hook: schedules the send so task events never wait on Telegram."""
    if kind not in HOOK_KINDS:
        return
    try:
        loop = _asyncio.get_running_loop()
    except RuntimeError:
        return
    job = loop.create_task(_dispatch(task_id, tasks_map.get(task_id), kind, dict(data or {}), n))
    _background.add(job)
    job.add_done_callback(_background.discard)


def install(task_queue, n=None):
    """Wrap task_queue.add_event/publish once. Nested calls fire the hook only once."""
    if getattr(task_queue, "_notify_installed", False):
        return

    def wrap(orig):
        def inner(task_id, kind, data, *args, **kwargs):
            global _depth
            if _depth:
                return orig(task_id, kind, data, *args, **kwargs)
            _depth += 1
            try:
                result = orig(task_id, kind, data, *args, **kwargs)
            finally:
                _depth -= 1
            _track(task_id, kind, data)
            on_event(task_id, kind, data, task_queue.TASKS, n)
            return result
        return inner

    task_queue.add_event = wrap(task_queue.add_event)
    task_queue.publish = wrap(task_queue.publish)
    task_queue._notify_installed = True


def _pending_id(task):
    pending = task.get("pending_permission")
    if isinstance(pending, dict):
        return str(pending.get("id") or pending.get("action_id") or "")
    return str(pending or "")


async def handle_update(body, task_queue, n=None):
    """Telegram button press. Accepted only for the request the task is waiting on."""
    n = n or notifier
    hit = n.resolve_callback(body)
    if not hit:
        return False
    task_id, request_id, decision, callback_id = hit
    task = task_queue.TASKS.get(task_id)
    if not task or not request_id or _waiting.get(task_id) != request_id:
        await n.answer(callback_id, "이미 처리됐거나 끝난 요청입니다")
        return False
    task["permissions"].append(decision)
    task_queue.add_event(task_id, "permission", {"decision": decision, "task_id": task_id, "via": "telegram"})
    await n.answer(callback_id, DECISION_TEXT[decision])
    return True
