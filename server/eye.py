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

import httpx

import storage

MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MAX_IMAGE_BYTES = 1_500_000  # 1.5MB after decoding
MAX_QUESTION = 1000
SOURCES = ("mac", "phone")
LOG_PATH = ".agent/eye/log.json"
MAX_LOG = 200
SYSTEM = ("너는 '하루 눈'이다. 사진을 보고 사용자의 질문에 한국어로 짧게(두세 문장 이내) 답해라. "
          "보이는 것만 말하고 안 보이면 안 보인다고 해라. 마지막 줄에 'SCENE: '으로 시작하는 화면 한 줄 설명을 붙여라.")

log = logging.getLogger("uvicorn.error")
_entries = None  # newest last; loaded from the store on first use
_lock = asyncio.Lock()


class EyeError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def check(body) -> tuple:
    """Validates the request body; returns (jpeg_base64, question, source, deep). Raises EyeError(400/413)."""
    if not isinstance(body, dict):
        raise EyeError(400, "invalid body")
    image, question, source, deep = body.get("image"), body.get("question"), body.get("source"), body.get("deep", False)
    if not isinstance(image, str) or not image:
        raise EyeError(400, "image (base64 jpeg) is required")
    if not isinstance(question, str) or not question.strip() or len(question) > MAX_QUESTION:
        raise EyeError(400, f"question is required (max {MAX_QUESTION} chars)")
    if source not in SOURCES:
        raise EyeError(400, "source must be mac or phone")
    if not isinstance(deep, bool):
        raise EyeError(400, "deep must be true or false")
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
    return image, question.strip(), source, deep


def payload(image: str, question: str, deep: bool) -> dict:
    body = {"model": MODEL, "stream": False,
            "messages": [{"role": "system", "content": SYSTEM},
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


async def ask(body) -> dict:
    image, question, source, deep = check(body)
    started = time.monotonic()
    reply = await call_model(payload(image, question, deep), 90 if deep else 45)
    seconds = round(time.monotonic() - started, 1)
    answer, scene = split_reply(reply)
    if not answer:
        raise EyeError(502, "model gave an empty answer")
    log.info("eye source=%s deep=%s 걸린초=%.1f", source, deep, seconds)
    await remember({"time": time.time(), "source": source, "question": question, "answer": answer, "scene": scene})
    return {"answer": answer, "model": MODEL, "seconds": seconds}
