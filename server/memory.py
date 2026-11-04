"""Topic memories stored in jun-files .agent/memory/ (one file per topic + index.json, one commit per change).
Small by design (<=200 entries, <=2000 chars each) so the whole index stays in memory."""
import json
import re
import secrets
import time

import httpx

import storage

MEM_DIR = ".agent/memory"
INDEX_PATH = f"{MEM_DIR}/index.json"
MAX_ENTRIES = 200
MAX_TOPIC = 60
MAX_CONTENT = 2000
PROMPT_CHARS = 3000
ID_RE = re.compile(r"^[a-z0-9-]{3,40}$")
_REMEMBER = re.compile(r"^\s*(?:기억해\s*줘?|기억해|remember(?:\s+that)?)\s*[:,]?\s+(.+)$", re.IGNORECASE | re.DOTALL)
_mem = None  # id -> entry {id, topic, content, created, updated}


class MemoryError_(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def valid_id(mid: str) -> bool:
    return bool(ID_RE.fullmatch(mid or ""))


async def _ensure():
    global _mem
    if _mem is None:
        text = await storage.read_file(INDEX_PATH)
        _mem = {e["id"]: e for e in json.loads(text)["memories"]} if text else {}
    return _mem


def _index_json() -> str:
    items = sorted(_mem.values(), key=lambda e: e["updated"], reverse=True)
    return json.dumps({"memories": items}, ensure_ascii=False, indent=1)


async def _commit(entry_id: str, entry, msg: str):
    """entry=None deletes the topic file. Raises if the commit fails (caller rolls back)."""
    files = {f"{MEM_DIR}/{entry_id}.json": None if entry is None else json.dumps(entry, ensure_ascii=False, indent=1),
             INDEX_PATH: _index_json()}
    async with httpx.AsyncClient(timeout=20) as c:
        await storage._commit_files(c, files, msg)


def _check(topic, content):
    topic, content = " ".join(str(topic or "").split()), str(content or "").strip()
    if not topic or not content:
        raise MemoryError_(400, "topic and content are required")
    if len(topic) > MAX_TOPIC or len(content) > MAX_CONTENT:
        raise MemoryError_(400, f"topic max {MAX_TOPIC} chars, content max {MAX_CONTENT} chars")
    return topic, content


async def list_all() -> list:
    await _ensure()
    return sorted(_mem.values(), key=lambda e: e["updated"], reverse=True)


async def get(mid: str):
    await _ensure()
    return _mem.get(mid) if valid_id(mid) else None


async def create(topic, content) -> dict:
    topic, content = _check(topic, content)
    await _ensure()
    if len(_mem) >= MAX_ENTRIES:
        raise MemoryError_(409, "memory is full")
    slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:20] or "m"
    now = time.time()
    entry = {"id": f"{slug}-{secrets.token_hex(3)}", "topic": topic, "content": content, "created": now, "updated": now}
    _mem[entry["id"]] = entry
    try:
        await _commit(entry["id"], entry, f"memory add {entry['id']}")
    except Exception:
        _mem.pop(entry["id"], None)
        raise
    return entry


async def update(mid: str, topic=None, content=None):
    await _ensure()
    old = _mem.get(mid) if valid_id(mid) else None
    if old is None:
        return None
    t, c = _check(old["topic"] if topic is None else topic, old["content"] if content is None else content)
    new = {**old, "topic": t, "content": c, "updated": time.time()}
    _mem[mid] = new
    try:
        await _commit(mid, new, f"memory edit {mid}")
    except Exception:
        _mem[mid] = old
        raise
    return new


async def delete(mid: str) -> bool:
    await _ensure()
    old = _mem.pop(mid, None) if valid_id(mid) else None
    if old is None:
        return False
    try:
        await _commit(mid, None, f"memory delete {mid}")
    except Exception:
        _mem[mid] = old
        raise
    return True


def extract_request(text: str):
    """'기억해줘: X' / 'remember that X' -> X (else None)."""
    m = _REMEMBER.match(text or "")
    return m.group(1).strip() if m else None


async def prompt_message():
    """System message with saved memories (newest first, capped), or None. Never raises."""
    try:
        items = await list_all()
    except Exception:
        return None
    lines, total = [], 0
    for e in items:
        line = f"- {e['topic']}: {e['content']}"
        if total + len(line) > PROMPT_CHARS:
            break
        lines.append(line)
        total += len(line)
    if not lines:
        return None
    return {"role": "system", "content": "What you remember about the user (saved memory; use only when relevant):\n" + "\n".join(lines)}


# ---- automatic suggestions ----
# Cheap gate first: only messages that talk about the user themself cost an LLM call.
_GATE = re.compile(r"나는|난 |내가|저는|제가|내 |제 |우리 |나의|항상|앞으로|좋아해|싫어해|선호|알레르기|"
                   r"\bI am\b|\bI'm\b|\bmy\b|\bI (like|love|prefer|hate|use|work|live)\b|\bwe\b", re.IGNORECASE)
_SENSITIVE = re.compile(r"password|passwd|비밀번호|비번|api[_ -]?key|token|secret|[A-Za-z0-9_\-]{24,}|\d{9,}", re.IGNORECASE)
SUGGEST_SYSTEM = (
    "You decide whether the user's message reveals a stable personal fact or preference worth remembering "
    "long-term (name, job, diet, tools they use, habits, goals, preferences). Do NOT save: one-off requests, "
    "questions, passwords, keys, payment or ID numbers, health details, or private facts about other people. "
    "Write topic and content in the same language as the user's message. "
    "Existing memory topics: {topics}. If a topic already exists, reuse the same topic name to update it. "
    'Reply with JSON only: {{"remember": false}} or '
    '{{"remember": true, "topic": "<=40 chars", "content": "one short sentence about the user"}}.')


async def suggest(user_text: str, answer: str = ""):
    """Maybe save one memory from this exchange. Returns the saved entry or None. Never raises."""
    import llm  # local import: llm -> router -> codex -> storage, avoids a cycle at module load
    try:
        if not _GATE.search(user_text or ""):
            return None
        topics = [e["topic"] for e in (await list_all())[:50]]
        out = llm.parse_json(await llm.ask(SUGGEST_SYSTEM.format(topics=json.dumps(topics, ensure_ascii=False)),
                                           f"User: {user_text[:800]}\nAssistant: {answer[:300]}", max_tokens=300))
        if not out or out.get("remember") is not True:
            return None
        topic, content = " ".join(str(out.get("topic", "")).split())[:MAX_TOPIC], str(out.get("content", "")).strip()[:MAX_CONTENT]
        if not topic or not content or _SENSITIVE.search(topic + " " + content):
            return None
        same = next((e for e in await list_all() if e["topic"].lower() == topic.lower()), None)
        if same:
            if same["content"].strip() == content:
                return None  # nothing new
            return await update(same["id"], content=content)
        return await create(topic, content)
    except Exception:
        return None
