"""Commit chat files to jun-files/.agent/chats/ via GitHub API, with local retry queue."""
import asyncio
import base64
import json
import logging
import os
import time
from pathlib import Path
import httpx

OWNER = os.environ.get("GITHUB_OWNER", "buriburiyj")
REPO = os.environ.get("GITHUB_REPO", "jun-files")
QUEUE = Path(os.environ.get("QUEUE_DIR", "/tmp/queue"))
API = "https://api.github.com"


def _headers():
    return {
        "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN', '')}",
        "Accept": "application/vnd.github+json",
    }


def _enqueue(name: str, path: str, content, meta=None):
    """Best-effort local retry queue; a read-only disk must never raise."""
    try:
        QUEUE.mkdir(parents=True, exist_ok=True)
        (QUEUE / f"{name}.json").write_text(json.dumps({"path": path, "content": content, "meta": meta}))
    except OSError as e:
        logging.getLogger("uvicorn.error").warning("queue write failed: %s", type(e).__name__)


async def _put(client: httpx.AsyncClient, path: str, content: str, msg: str):
    url = f"{API}/repos/{OWNER}/{REPO}/contents/{path}"
    sha = None
    g = await client.get(url, headers=_headers())
    if g.status_code == 200:
        sha = g.json()["sha"]
    body = {"message": msg, "content": base64.b64encode(content.encode()).decode()}
    if sha:
        body["sha"] = sha
    r = await client.put(url, headers=_headers(), json=body)
    r.raise_for_status()


async def read_file(path: str):
    """Return file text from the store repo, or None if missing. Raises on other errors."""
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.get(f"{API}/repos/{OWNER}/{REPO}/contents/{path}", headers=_headers())
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return base64.b64decode(r.json()["content"]).decode()


async def commit_file(path: str, content: str, msg: str, queue_name: str) -> bool:
    """Commit one file; on failure queue locally under queue_name (newer content overwrites older)."""
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            await _put(c, path, content, msg)
        return True
    except Exception as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        logging.getLogger("uvicorn.error").warning("commit %s failed: %s status=%s", path, type(e).__name__, status)
        _enqueue(queue_name, path, content)
        return False


async def put_bytes(client: httpx.AsyncClient, path: str, data: bytes, msg: str):
    """Create a binary file in the store repo (raises on failure)."""
    url = f"{API}/repos/{OWNER}/{REPO}/contents/{path}"
    body = {"message": msg, "content": base64.b64encode(data).decode(), "branch": os.environ.get("GITHUB_BRANCH", "main")}
    r = await client.put(url, headers=_headers(), json=body)
    r.raise_for_status()


async def read_bytes(path: str):
    """Raw file bytes from the store repo, or None if missing."""
    h = dict(_headers())
    h["Accept"] = "application/vnd.github.raw+json"
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(f"{API}/repos/{OWNER}/{REPO}/contents/{path}", headers=h)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.content


BRANCH = os.environ.get("GITHUB_BRANCH", "main")
CHATS_DIR = ".agent/chats"
INDEX_PATH = f"{CHATS_DIR}/index.json"
_index = None  # id -> meta {id,title,created,updated,preview}; small, kept in memory


def _safe_id(chat_id: str) -> str:
    return "".join(c for c in chat_id if c.isalnum() or c in "-_")[:64] or "chat"


def _chat_path(safe: str) -> str:
    return f"{CHATS_DIR}/{safe}.json"


_commit_lock = asyncio.Lock()


async def _commit_files(client: httpx.AsyncClient, files: dict, msg: str):
    """One commit for several files via the Git Data API. A value of None deletes the file.
    Serialized, because two commits built on the same head would conflict."""
    async with _commit_lock:
        await _commit_files_unlocked(client, files, msg)


async def _commit_files_unlocked(client: httpx.AsyncClient, files: dict, msg: str):
    base = f"{API}/repos/{OWNER}/{REPO}"
    h = _headers()
    ref = await client.get(f"{base}/git/ref/heads/{BRANCH}", headers=h)
    ref.raise_for_status()
    head = ref.json()["object"]["sha"]
    c = await client.get(f"{base}/git/commits/{head}", headers=h)
    c.raise_for_status()
    entries = []
    for path, content in files.items():
        e = {"path": path, "mode": "100644", "type": "blob"}
        if content is None:
            e["sha"] = None
        else:
            e["content"] = content
        entries.append(e)
    t = await client.post(f"{base}/git/trees", headers=h,
                          json={"base_tree": c.json()["tree"]["sha"], "tree": entries})
    t.raise_for_status()
    nc = await client.post(f"{base}/git/commits", headers=h,
                           json={"message": msg, "tree": t.json()["sha"], "parents": [head]})
    nc.raise_for_status()
    u = await client.patch(f"{base}/git/refs/heads/{BRANCH}", headers=h, json={"sha": nc.json()["sha"]})
    u.raise_for_status()


def _recent_first() -> list:
    # reversed() first: for equal timestamps the most recently saved chat wins (sort is stable)
    return sorted(reversed(list(_index.values())), key=lambda m: m["updated"], reverse=True)


def _index_json() -> str:
    return json.dumps({"chats": _recent_first()}, ensure_ascii=False, indent=1)


async def _ensure_index():
    global _index
    if _index is None:
        text = await read_file(INDEX_PATH)
        _index = {m["id"]: m for m in json.loads(text)["chats"]} if text else {}


def _title_from(messages: list) -> str:
    for m in messages:
        if m.get("role") == "user" and m.get("content"):
            t = " ".join(str(m["content"]).split())
            return t[:40] + ("…" if len(t) > 40 else "")
    return "New chat"


def _preview_from(messages: list) -> str:
    for m in reversed(messages):
        if m.get("role") == "assistant" and m.get("content"):
            return " ".join(str(m["content"]).split())[:100]
    return ""


async def save_chat(chat_id: str, data: dict):
    """One commit per answer: the chat file and index.json together.
    Returns (saved, meta). On failure the chat is queued locally and retried."""
    safe = _safe_id(chat_id)
    messages = data.get("messages", [])
    now = int(time.time())
    content = json.dumps({"id": safe, "messages": messages}, ensure_ascii=False, indent=1)
    try:
        await _ensure_index()
    except Exception:
        # Never write an index built from nothing: queue the chat, merge into the real index later.
        meta = {"id": safe, "title": _title_from(messages), "created": now, "updated": now,
                "preview": _preview_from(messages)}
        _enqueue(safe, _chat_path(safe), content, meta=meta)
        return False, meta
    old = _index.get(safe, {})
    meta = {"id": safe, "title": old.get("title") or _title_from(messages),
            "created": old.get("created", now), "updated": now, "preview": _preview_from(messages)}
    _index.pop(safe, None)
    _index[safe] = meta
    ok = await _commit(_chat_path(safe), content, safe, f"chat {safe}", meta)
    return ok, meta


async def _commit(path: str, content, queue_name: str, msg: str, meta=None) -> bool:
    """Commit one chat file (None = delete) together with index.json; queue locally on failure."""
    files = {path: content, INDEX_PATH: _index_json()}
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            await _commit_files(c, files, msg)
        return True
    except Exception as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        logging.getLogger("uvicorn.error").warning("commit %s failed: %s status=%s", path, type(e).__name__, status)
        _enqueue(queue_name, path, content, meta=meta)
        return False


async def list_chats(q: str = "", limit: int = 100) -> list:
    await _ensure_index()
    items = _recent_first()
    if q:
        ql = q.lower()
        items = [m for m in items if ql in m["title"].lower() or ql in m.get("preview", "").lower()]
    return items[:limit]


async def get_chat(chat_id: str):
    safe = _safe_id(chat_id)
    await _ensure_index()
    text = await read_file(_chat_path(safe))
    if text is None:
        return None
    d = json.loads(text)
    d["title"] = _index.get(safe, {}).get("title", "")
    return d


async def rename_chat(chat_id: str, title: str) -> bool:
    safe = _safe_id(chat_id)
    await _ensure_index()
    if safe not in _index:
        return False
    _index[safe]["title"] = title.strip()[:100] or _index[safe]["title"]
    await _commit_index_only(f"rename {safe}", safe)
    return True


async def delete_chat(chat_id: str) -> bool:
    safe = _safe_id(chat_id)
    await _ensure_index()
    if safe not in _index:
        return False
    del _index[safe]
    await _commit(_chat_path(safe), None, f"del-{safe}", f"delete {safe}")
    return True


async def _commit_index_only(msg: str, queue_name: str):
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            await _commit_files(c, {INDEX_PATH: _index_json()}, msg)
    except Exception as e:
        logging.getLogger("uvicorn.error").warning("index commit failed: %s", type(e).__name__)
        _enqueue(f"idx-{queue_name}", INDEX_PATH, _index_json())


async def flush_queue() -> int:
    if not QUEUE.exists():
        return 0
    done = 0
    async with httpx.AsyncClient(timeout=20) as c:
        for f in sorted(QUEUE.glob("*.json")):
            try:
                item = json.loads(f.read_text())
                path = item["path"]
                if path.startswith(f"{CHATS_DIR}/") and path != INDEX_PATH:
                    # chat file (or delete): rebuild index.json from the current index at flush time
                    await _ensure_index()
                    cid = Path(path).stem
                    if item["content"] is None:
                        _index.pop(cid, None)
                    elif item.get("meta") and item["meta"]["updated"] >= _index.get(cid, {}).get("updated", 0):
                        _index[cid] = item["meta"]
                    await _commit_files(c, {path: item["content"], INDEX_PATH: _index_json()}, f"chat {f.stem} (retry)")
                elif path == INDEX_PATH:
                    await _ensure_index()
                    await _commit_files(c, {INDEX_PATH: _index_json()}, "index (retry)")
                else:
                    await _put(c, path, item["content"], f"{f.stem} (retry)")
                f.unlink()
                done += 1
            except Exception:
                break
    return done


async def retry_loop(interval: int = 60):
    while True:
        await asyncio.sleep(interval)
        await flush_queue()
