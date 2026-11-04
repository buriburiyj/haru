"""Projects: instructions + text files that are given to the model in every chat of the project.
Stored in jun-files .agent/projects/<id>.json (the whole project) and index.json (list view), one commit per change."""
import json
import re
import secrets
import time
from collections import OrderedDict

import httpx

import storage

PROJ_DIR = ".agent/projects"
INDEX_PATH = f"{PROJ_DIR}/index.json"
MAX_PROJECTS = 50
MAX_NAME = 60
MAX_INSTRUCTIONS = 4000
MAX_FILES = 10
MAX_FILE_NAME = 80
MAX_FILE_CHARS = 20_000
MAX_TOTAL_CHARS = 100_000
PROMPT_CHARS = 30_000  # what goes into one chat prompt
ID_RE = re.compile(r"^[a-z0-9-]{3,40}$")
_idx = None  # id -> meta
_cache: "OrderedDict[str, dict]" = OrderedDict()  # last few full projects
_CACHE_MAX = 5


class ProjectError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def valid_id(pid: str) -> bool:
    return bool(ID_RE.fullmatch(pid or ""))


def _meta(p: dict) -> dict:
    return {"id": p["id"], "name": p["name"], "instructions_preview": p["instructions"][:100],
            "files": [f["name"] for f in p["files"]], "created": p["created"], "updated": p["updated"]}


async def _ensure():
    global _idx
    if _idx is None:
        text = await storage.read_file(INDEX_PATH)
        _idx = {m["id"]: m for m in json.loads(text)["projects"]} if text else {}
    return _idx


def _index_json() -> str:
    items = sorted(_idx.values(), key=lambda m: m["updated"], reverse=True)
    return json.dumps({"projects": items}, ensure_ascii=False, indent=1)


async def _commit(pid: str, project, msg: str):
    files = {f"{PROJ_DIR}/{pid}.json": None if project is None else json.dumps(project, ensure_ascii=False, indent=1),
             INDEX_PATH: _index_json()}
    async with httpx.AsyncClient(timeout=20) as c:
        await storage._commit_files(c, files, msg)


def _check(name, instructions, files):
    name = " ".join(str(name or "").split())
    instructions = str(instructions or "").strip()
    if not name:
        raise ProjectError(400, "name is required")
    if len(name) > MAX_NAME or len(instructions) > MAX_INSTRUCTIONS:
        raise ProjectError(400, f"name max {MAX_NAME} chars, instructions max {MAX_INSTRUCTIONS} chars")
    clean, seen, total = [], set(), 0
    for f in files or []:
        if not isinstance(f, dict):
            raise ProjectError(400, "bad file entry")
        fname, content = str(f.get("name", "")).strip(), f.get("content")
        if not fname or len(fname) > MAX_FILE_NAME or re.search(r"[/\\\x00]", fname) or not isinstance(content, str):
            raise ProjectError(400, "file needs a name (no slashes) and text content")
        if len(content) > MAX_FILE_CHARS:
            raise ProjectError(413, f"file too large (max {MAX_FILE_CHARS} chars)")
        if fname.lower() in seen:
            raise ProjectError(400, "duplicate file name")
        seen.add(fname.lower())
        total += len(content)
        clean.append({"name": fname, "content": content})
    if len(clean) > MAX_FILES or total > MAX_TOTAL_CHARS:
        raise ProjectError(413, f"max {MAX_FILES} files and {MAX_TOTAL_CHARS} chars in total")
    return name, instructions, clean


def _remember(p: dict):
    _cache[p["id"]] = p
    _cache.move_to_end(p["id"])
    while len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)


async def list_all() -> list:
    await _ensure()
    return sorted(_idx.values(), key=lambda m: m["updated"], reverse=True)


async def get(pid: str):
    if not valid_id(pid):
        return None
    await _ensure()
    if pid not in _idx:
        return None
    if pid in _cache:
        return _cache[pid]
    text = await storage.read_file(f"{PROJ_DIR}/{pid}.json")
    if text is None:
        return None
    p = json.loads(text)
    _remember(p)
    return p


async def create(name, instructions="", files=None) -> dict:
    name, instructions, files = _check(name, instructions, files)
    await _ensure()
    if len(_idx) >= MAX_PROJECTS:
        raise ProjectError(409, "too many projects")
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:20] or "p"
    now = time.time()
    p = {"id": f"{slug}-{secrets.token_hex(3)}", "name": name, "instructions": instructions, "files": files,
         "created": now, "updated": now}
    _idx[p["id"]] = _meta(p)
    try:
        await _commit(p["id"], p, f"project add {p['id']}")
    except Exception:
        _idx.pop(p["id"], None)
        raise
    _remember(p)
    return p


async def update(pid: str, name=None, instructions=None, files=None):
    old = await get(pid)
    if old is None:
        return None
    n, i, f = _check(old["name"] if name is None else name,
                     old["instructions"] if instructions is None else instructions,
                     old["files"] if files is None else files)
    new = {**old, "name": n, "instructions": i, "files": f, "updated": time.time()}
    prev_meta = _idx[pid]
    _idx[pid] = _meta(new)
    try:
        await _commit(pid, new, f"project edit {pid}")
    except Exception:
        _idx[pid] = prev_meta
        raise
    _remember(new)
    return new


async def add_file(pid: str, name: str, content):
    """Add a file, or replace the one with the same name."""
    old = await get(pid)
    if old is None:
        return None
    files = [f for f in old["files"] if f["name"].lower() != str(name).strip().lower()] + [{"name": name, "content": content}]
    return await update(pid, files=files)


async def remove_file(pid: str, name: str):
    old = await get(pid)
    if old is None:
        return None
    files = [f for f in old["files"] if f["name"] != name]
    if len(files) == len(old["files"]):
        raise ProjectError(404, "file not found")
    return await update(pid, files=files)


async def delete(pid: str) -> bool:
    """Call only after the user confirmed in the UI. Chats of the project are kept."""
    await _ensure()
    if not valid_id(pid) or pid not in _idx:
        return False
    meta = _idx.pop(pid)
    try:
        await _commit(pid, None, f"project delete {pid}")
    except Exception:
        _idx[pid] = meta
        raise
    _cache.pop(pid, None)
    return True


def prompt_message(p: dict) -> dict:
    """System message with the project's instructions and files (capped)."""
    parts = [f"You are working inside the project \"{p['name']}\"."]
    if p["instructions"]:
        parts.append("Project instructions (follow them):\n" + p["instructions"])
    budget = PROMPT_CHARS - sum(len(x) for x in parts)
    for f in p["files"]:
        if budget <= 200:
            parts.append("(more project files were left out to keep the prompt short)")
            break
        text = f["content"][:budget]
        parts.append(f"Project file \"{f['name']}\"" + (" (cut)" if len(text) < len(f["content"]) else "") + f":\n{text}")
        budget -= len(text)
    return {"role": "system", "content": "\n\n".join(parts)}
