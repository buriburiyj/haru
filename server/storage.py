"""Commit chat files to jun-files/.agent/chats/ via GitHub API, with local retry queue."""
import asyncio
import base64
import json
import os
import time
from pathlib import Path
import httpx

OWNER = os.environ.get("GITHUB_OWNER", "buriburiyj")
REPO = os.environ.get("GITHUB_REPO", "jun-files")
QUEUE = Path(os.environ.get("QUEUE_DIR", Path(__file__).parent / "queue"))
API = "https://api.github.com"


def _headers():
    return {
        "Authorization": f"Bearer {os.environ.get('GITHUB_TOKEN', '')}",
        "Accept": "application/vnd.github+json",
    }


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


async def save_chat(chat_id: str, data: dict) -> bool:
    """Commit once per answer. On failure, queue locally. Returns True if committed."""
    safe = "".join(c for c in chat_id if c.isalnum() or c in "-_")[:64] or "chat"
    path = f".agent/chats/{safe}.json"
    content = json.dumps(data, ensure_ascii=False, indent=1)
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            await _put(c, path, content, f"chat {safe}")
        return True
    except Exception:
        QUEUE.mkdir(parents=True, exist_ok=True)
        (QUEUE / f"{safe}.json").write_text(json.dumps({"path": path, "content": content}))
        return False


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
    except Exception:
        QUEUE.mkdir(parents=True, exist_ok=True)
        (QUEUE / f"{queue_name}.json").write_text(json.dumps({"path": path, "content": content}))
        return False


async def flush_queue() -> int:
    if not QUEUE.exists():
        return 0
    done = 0
    async with httpx.AsyncClient(timeout=20) as c:
        for f in sorted(QUEUE.glob("*.json")):
            try:
                item = json.loads(f.read_text())
                await _put(c, item["path"], item["content"], f"chat {f.stem} (retry)")
                f.unlink()
                done += 1
            except Exception:
                break
    return done


async def retry_loop(interval: int = 60):
    while True:
        await asyncio.sleep(interval)
        await flush_queue()
