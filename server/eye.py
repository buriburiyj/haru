"""Haru Eye: one photo + a question -> a short Korean answer from the NVIDIA vision model.
Only time, source, question, answer and a one-line scene description are remembered (never the photo)."""
import asyncio
import base64
import binascii
import json
import logging
import os
import re
import time
from collections import OrderedDict, deque

import httpx

import router
import search
import storage

MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MAX_IMAGE_BYTES = 1_500_000  # 1.5MB after decoding
MAX_QUESTION = 1000
SOURCES = ("mac", "phone")
LOG_PATH = ".agent/eye/log.json"
MAX_LOG = 200
VOICE = ("답은 소리로 읽기 좋게 한국어 2~3문장으로, 마크다운·목록·링크·이모지 없이 평범한 말투로 써라.")
SYSTEM = ("너는 '하루 눈'이다. 사진을 보고 사용자의 질문에 답해라. " + VOICE +
          " 보이는 것만 말하고 안 보이면 안 보인다고 해라. 마지막 줄에 'SCENE: '으로 시작하는 화면 한 줄 설명을 붙여라.")
TEXT_SYSTEM = ("너는 휴대폰으로 말을 거는 비서 '하루'다. " + VOICE +
               " 아래 참고 자료에 있는 내용만 사실로 말하고, 모르면 모른다고 해라.")
PLAN_SYSTEM = ("사용자 말을 보고 JSON 객체 하나로만 답해라: "
               '{"past": 방금이 아니라 \'아까/전에 본 것\'을 묻는가(true/false), '
               '"need_photo": 지금 눈앞의 것을 봐야 답할 수 있는가(이거/저거/이게 뭐야/읽어 줘/보여 등, true/false), '
               '"search": 최신 정보나 사실 확인이 필요하면 검색어, 아니면 빈 문자열}. '
               "past가 true면 need_photo는 false.")
NEED_PHOTO_WORDS = re.compile(r"이거|저거|이게|저게|이것|저것|뭐야|뭐예요|읽어|보여|사진|이 글|저 글|여기")
PAST_WORDS = re.compile(r"아까|전에|방금|조금 전|좀 전|지난번")
SESSION_TURNS = 6
MAX_SESSIONS = 100

log = logging.getLogger("uvicorn.error")
_entries = None  # newest last; loaded from the store on first use
_lock = asyncio.Lock()
_sessions = OrderedDict()  # session id -> deque of (question, answer), last SESSION_TURNS; memory only


class EyeError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def check(body) -> tuple:
    """Validates the request body; returns (jpeg_base64 or None, question, source, deep, session). Raises EyeError(400/413)."""
    if not isinstance(body, dict):
        raise EyeError(400, "invalid body")
    image, question, deep = body.get("image"), body.get("question"), body.get("deep", False)
    source = body.get("source", "phone")  # the phone-only talk sends no source
    session = body.get("session")
    if session is not None and (not isinstance(session, str) or not 0 < len(session) <= 64):
        raise EyeError(400, "session must be a string of 1-64 chars")
    if image is not None and (not isinstance(image, str) or not image):
        raise EyeError(400, "image must be a base64 jpeg when given")
    if not isinstance(question, str) or not question.strip() or len(question) > MAX_QUESTION:
        raise EyeError(400, f"question is required (max {MAX_QUESTION} chars)")
    if source not in SOURCES:
        raise EyeError(400, "source must be mac or phone")
    if not isinstance(deep, bool):
        raise EyeError(400, "deep must be true or false")
    if image is None:
        return None, question.strip(), source, deep, session
    if image.startswith("data:"):
        image = image.split(",", 1)[-1]
    if len(image) * 3 // 4 > MAX_IMAGE_BYTES + 3:  # cheap check before decoding
        raise EyeError(413, "image is larger than 1.5MB")
    try:
        raw = base64.b64decode(image, validate=True)
    except (binascii.Error, ValueError):
        raise EyeError(400, "image is not valid base64")
    if len(raw) > MAX_IMAGE_BYTES:
        raise EyeError(413, "image is larger than 1.5MB")
    if not raw.startswith(b"\xff\xd8"):
        raise EyeError(400, "image must be a jpeg")
    return image, question.strip(), source, deep, session


def payload(image: str, question: str, deep: bool, history=()) -> dict:
    earlier = [{"role": r, "content": t} for q, a in history for r, t in (("user", q), ("assistant", a))]
    body = {"model": MODEL, "stream": False,
            "messages": [{"role": "system", "content": SYSTEM}, *earlier,
                         {"role": "user", "content": [{"type": "text", "text": question},
                                                      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + image}}]}]}
    if deep:
        body.update(max_tokens=2000, chat_template_kwargs={"enable_thinking": True})
    else:
        body.update(max_tokens=600, chat_template_kwargs={"enable_thinking": False})
    return body


async def call_model(body: dict, timeout: float) -> str:
    """POSTs to NVIDIA and returns the message text. Tests replace this with a fake."""
    key = os.environ.get("NVIDIA_API_KEY", "")
    if not key:
        raise EyeError(503, "model key is not set")
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(URL, headers={"Authorization": f"Bearer {key}"}, json=body)
    except httpx.TimeoutException:
        raise EyeError(504, "model timeout")
    except httpx.HTTPError as exc:
        raise EyeError(502, f"model unreachable ({type(exc).__name__})")
    if r.status_code >= 400:
        raise EyeError(502, f"model error http {r.status_code}")
    try:
        return r.json()["choices"][0]["message"].get("content") or ""
    except (ValueError, KeyError, IndexError, TypeError):
        raise EyeError(502, "model reply unreadable")


def split_reply(text: str) -> tuple:
    """-> (answer, scene). Drops <think> blocks; the last SCENE: line becomes the one-line description."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    scene = ""
    lines = text.splitlines()
    for i in range(len(lines) - 1, -1, -1):
        m = re.match(r"\s*\**\s*SCENE\s*:\**\s*(.*)$", lines[i], re.I)
        if m:
            scene = m.group(1).strip()
            lines.pop(i)
            break
    answer = "\n".join(lines).strip()
    return answer, (scene or answer.split("\n")[0])[:200]


async def _load():
    global _entries
    if _entries is None:
        text = await storage.read_file(LOG_PATH)
        _entries = json.loads(text).get("entries", []) if text else []
    return _entries


async def remember(entry: dict) -> bool:
    """Appends one entry (no photo) and commits the log through the normal store (local retry queue on failure)."""
    async with _lock:
        try:
            entries = await _load()
        except Exception as exc:  # unreadable store: do not overwrite what we could not read
            log.warning("eye log not saved: %s", type(exc).__name__)
            return False
        entries.append(entry)
        del entries[:-MAX_LOG]
        return await storage.commit_file(LOG_PATH, json.dumps({"entries": entries}, ensure_ascii=False, indent=1),
                                         "eye: log", "eye-log")


async def recent(limit: int = 20) -> list:
    async with _lock:
        try:
            entries = await _load()
        except Exception as exc:
            log.warning("eye log not readable: %s", type(exc).__name__)
            raise EyeError(503, "memory store unavailable")
        return list(reversed(entries[-max(1, min(limit, MAX_LOG)):]))


def clean(text: str) -> str:
    """Makes an answer fit for reading aloud: no markdown, links, citations or line breaks."""
    text = re.sub(r"\[([^\]]*)\]\(https?://[^)]*\)", r"\1", text or "")
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\[\d+\]", "", text)
    text = re.sub(r"^\s*(?:#{1,6}|[-*•]|\d+[.)])\s+", "", text, flags=re.M)
    text = re.sub(r"[*_`#>]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


async def llm(messages: list, mode: str = "easy") -> tuple:
    """Fast text model through the router (Groq, then NVIDIA). -> (text, model id). Tests replace this with a fake."""
    model, parts = "", []
    async for kind, value in router.route(messages, mode):
        if kind == "model":
            model = value
        elif kind == "delta":
            parts.append(value)
    return "".join(parts).strip(), model


def read_plan(text: str, question: str) -> dict:
    """The planner's JSON, or a keyword guess when it cannot be read."""
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        d = json.loads(m.group(0)) if m else None
    except ValueError:
        d = None
    if not isinstance(d, dict):
        past = bool(PAST_WORDS.search(question))
        return {"past": past, "need_photo": not past and bool(NEED_PHOTO_WORDS.search(question)), "search": ""}
    past = d.get("past") is True
    query = d.get("search") if isinstance(d.get("search"), str) else ""
    return {"past": past, "need_photo": d.get("need_photo") is True and not past, "search": query.strip()[:300]}


def history_of(session) -> list:
    return list(_sessions.get(session, ())) if session else []


def remember_turn(session, question: str, answer: str):
    if not session:
        return
    turns = _sessions.pop(session, None) or deque(maxlen=SESSION_TURNS)
    turns.append((question, answer))
    _sessions[session] = turns  # most recently used last
    while len(_sessions) > MAX_SESSIONS:
        _sessions.popitem(last=False)


def past_context(entries: list) -> str:
    """The eye log as lines for the model: how long ago, what was asked, what was seen."""
    now = time.time()
    lines = []
    for e in entries:
        mins = max(0, int((now - float(e.get("time", now))) / 60))
        ago = "방금" if mins < 1 else f"{mins}분 전" if mins < 120 else f"{mins // 60}시간 전"
        lines.append(f"- {ago}: 질문 \"{e.get('question', '')}\" / 본 것: {e.get('scene', '')} / 답: {e.get('answer', '')[:150]}")
    return "\n".join(lines) if lines else "(저장된 기록이 없음)"


async def ask_text(question: str, session) -> tuple:
    """No photo: decide (fast model), then answer from the eye log, a web search or plain knowledge.
    -> (answer, need_photo, model)."""
    plan_text, model = await llm([{"role": "system", "content": PLAN_SYSTEM}, {"role": "user", "content": question}])
    plan = read_plan(plan_text, question)
    if plan["need_photo"]:
        return "", True, model
    context = ""
    if plan["past"]:
        context = "아까 본 것 기록(최근 것부터):\n" + past_context(await recent(20))
    elif plan["search"]:
        results = await search.search(plan["search"])
        if results:
            context = "웹 검색 결과(링크는 말하지 마라):\n" + "\n".join(f"- {r['title']}: {r['snippet']}" for r in results)
    system = TEXT_SYSTEM + (f"\n\n오늘은 {time.strftime('%Y-%m-%d', time.gmtime())}." if plan["search"] else "") + (f"\n\n{context}" if context else "")
    earlier = [{"role": r, "content": t} for q, a in history_of(session) for r, t in (("user", q), ("assistant", a))]
    text, model = await llm([{"role": "system", "content": system}, *earlier, {"role": "user", "content": question}])
    answer = clean(text)
    if not answer:
        raise EyeError(503, "no model answered")
    return answer, False, model or ""


async def ask(body) -> dict:
    image, question, source, deep, session = check(body)
    started = time.monotonic()
    if image is None:
        answer, need_photo, model = await ask_text(question, session)
        seconds = round(time.monotonic() - started, 1)
        log.info("eye text need_photo=%s 걸린초=%.1f", need_photo, seconds)
        if not need_photo:
            remember_turn(session, question, answer)
        return {"answer": answer, "need_photo": need_photo, "model": model, "seconds": seconds}
    reply = await call_model(payload(image, question, deep, history_of(session)), 90 if deep else 45)
    seconds = round(time.monotonic() - started, 1)
    answer, scene = split_reply(reply)
    answer = clean(answer)
    if not answer:
        raise EyeError(502, "model gave an empty answer")
    log.info("eye source=%s deep=%s 걸린초=%.1f", source, deep, seconds)
    await remember({"time": time.time(), "source": source, "question": question, "answer": answer, "scene": scene})
    remember_turn(session, question, answer)
    return {"answer": answer, "need_photo": False, "model": MODEL, "seconds": seconds}
