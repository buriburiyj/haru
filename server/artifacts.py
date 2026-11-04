"""Artifacts: code/HTML blocks from answers, saved in jun-files .agent/artifacts/ (one file each + index.json).
If a commit fails, the files wait in memory (capped) and ride along with the next successful commit."""
import hashlib
import json
import re
import time

import httpx

import storage

ART_DIR = ".agent/artifacts"
INDEX_PATH = f"{ART_DIR}/index.json"
MAX_PER_ANSWER = 5
MAX_CHARS = 200_000
MIN_LINES = 10  # other languages must be at least this long; html and svg are always kept
ALWAYS = {"html", "svg"}
LANGS = {"html", "svg", "jsx", "tsx", "javascript", "js", "typescript", "ts", "python", "py", "css", "bash", "sh",
         "sql", "java", "c", "cpp", "go", "rust", "rs", "json", "yaml", "markdown", "md", "php", "ruby", "swift", "kotlin"}
PENDING_MAX_CHARS = 2_000_000
ID_RE = re.compile(r"^[0-9a-f]{12}$")
_BLOCK = re.compile(r"```([A-Za-z0-9_+#.-]*)[ \t]*\n(.*?)\n?```", re.DOTALL)
_idx = None  # id -> meta
_pending_files: dict = {}  # path -> content, waiting for a successful commit
_pending_meta: dict = {}  # id -> meta, merged into the index when it can be loaded


def valid_id(aid: str) -> bool:
    return bool(ID_RE.fullmatch(aid or ""))


def _title(lang: str, code: str) -> str:
    m = re.search(r"<title>(.*?)</title>", code, re.IGNORECASE | re.DOTALL) or re.search(r"<h1[^>]*>(.*?)</h1>", code, re.IGNORECASE | re.DOTALL)
    if m and m.group(1).strip():
        return " ".join(re.sub(r"<[^>]+>", "", m.group(1)).split())[:60] or lang
    first = code.strip().splitlines()[0] if code.strip() else ""
    c = re.match(r"^\s*(?://|#|--|/\*+|<!--)\s*(.+?)\s*(?:\*/|-->)?\s*$", first)
    return (c.group(1)[:60] if c and lang not in ("html", "svg") else f"{lang or 'code'} snippet")


def extract(text: str) -> list:
    """Artifact-worthy fenced blocks of an answer: [{language, title, content}]."""
    out = []
    for lang, code in _BLOCK.findall(text or ""):
        lang_l = lang.lower()
        if lang_l not in LANGS or not code.strip() or len(code) > MAX_CHARS:
            continue
        if lang_l not in ALWAYS and code.count("\n") + 1 < MIN_LINES:
            continue
        out.append({"language": lang_l, "title": _title(lang_l, code), "content": code})
        if len(out) >= MAX_PER_ANSWER:
            break
    return out


async def _ensure():
    global _idx
    if _idx is None:
        text = await storage.read_file(INDEX_PATH)
        _idx = {m["id"]: m for m in json.loads(text)["artifacts"]} if text else {}
    for aid, m in list(_pending_meta.items()):
        _idx.setdefault(aid, m)
    return _idx


def _index_json() -> str:
    items = sorted(_idx.values(), key=lambda m: m["created"], reverse=True)
    return json.dumps({"artifacts": items}, ensure_ascii=False, indent=1)


def _hold(files: dict):
    _pending_files.update(files)
    while sum(len(v or "") for v in _pending_files.values()) > PENDING_MAX_CHARS and len(_pending_files) > 1:
        _pending_files.pop(next(iter(_pending_files)))  # drop the oldest


async def _commit(new_files: dict, msg: str) -> bool:
    files = {**_pending_files, **new_files}
    if _idx is not None:
        files[INDEX_PATH] = _index_json()
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            await storage._commit_files(c, files, msg)
    except Exception:
        _hold({k: v for k, v in new_files.items()})
        return False
    _pending_files.clear()
    _pending_meta.clear()
    return True


async def save(chat_id: str, text: str):
    """Save the artifacts found in `text`. Returns (metas, saved). Never raises; same content in the same chat is stored once."""
    found = extract(text)
    if not found:
        return [], True
    safe_chat = storage._safe_id(chat_id)
    now = time.time()
    metas, files = [], {}
    try:
        index_ok = True
        try:
            await _ensure()
        except Exception:
            index_ok = False
        for a in found:
            aid = hashlib.sha1(f"{safe_chat}\n{a['content']}".encode()).hexdigest()[:12]
            if index_ok and aid in _idx:
                continue  # regenerated answer with the same block
            meta = {"id": aid, "title": a["title"], "language": a["language"], "chat_id": safe_chat, "created": now,
                    "size": len(a["content"])}
            metas.append(meta)
            files[f"{ART_DIR}/{aid}.json"] = json.dumps({**meta, "content": a["content"]}, ensure_ascii=False)
            if index_ok:
                _idx[aid] = meta
            else:
                _pending_meta[aid] = meta
        if not metas:
            return [], True
        if not index_ok:
            _hold(files)  # never write an index built from nothing
            return metas, False
        return metas, await _commit(files, f"artifacts {safe_chat}")
    except Exception:
        return metas, False


async def list_all(chat_id: str = "", limit: int = 200) -> list:
    await _ensure()
    items = sorted(_idx.values(), key=lambda m: m["created"], reverse=True)
    if chat_id:
        items = [m for m in items if m["chat_id"] == storage._safe_id(chat_id)]
    return items[:limit]


async def get(aid: str):
    if not valid_id(aid):
        return None
    await _ensure()
    path = f"{ART_DIR}/{aid}.json"
    text = _pending_files.get(path) or await storage.read_file(path)
    return json.loads(text) if text else None


async def delete(aid: str) -> bool:
    """Call only after the user confirmed in the UI."""
    await _ensure()
    if not valid_id(aid) or aid not in _idx:
        return False
    meta = _idx.pop(aid)
    _pending_files.pop(f"{ART_DIR}/{aid}.json", None)
    _pending_meta.pop(aid, None)
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            await storage._commit_files(c, {f"{ART_DIR}/{aid}.json": None, INDEX_PATH: _index_json()}, f"artifact delete {aid}")
    except Exception:
        _idx[aid] = meta
        raise
    return True
