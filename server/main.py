import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import webauthn
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import PublicKeyCredentialDescriptor

import artifacts
import codex
import connector
import llm
import memory
import projects
import router
import search
import usage
import storage
import uploads
import tasks as task_queue

log = logging.getLogger("uvicorn.error")

ORIGIN = "https://buriburiyj.github.io"
RP_ID = "buriburiyj.github.io"
RP_NAME = "Haru"
CHALLENGE_TTL = 300
SESSION_TTL = 60 * 60 * 24 * 30
CRED_FILE = Path(os.environ.get("CRED_FILE", "/tmp/credentials.json"))
CRED_REMOTE = os.environ.get("CRED_REMOTE_PATH", ".agent/credentials.json")  # public keys only
PUBLIC = {"/health", "/auth/register/options", "/auth/register/verify", "/auth/login/options", "/auth/login/verify"}

app = FastAPI()


def _secret() -> bytes:
    return os.environ.get("SESSION_SECRET", "").encode() or b"dev-only-insecure"


def _sign(exp: int) -> str:
    sig = hmac.new(_secret(), str(exp).encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def _valid(tok: str) -> bool:
    try:
        exp, sig = tok.split(".", 1)
        ok = hmac.compare_digest(sig, _sign(int(exp)).split(".", 1)[1])
        return ok and int(exp) > time.time()
    except Exception:
        return False


def _bearer(request: Request) -> str:
    h = request.headers.get("authorization", "")
    return h[7:] if h.lower().startswith("bearer ") else ""


def _session_ok(request: Request) -> bool:
    return _valid(_bearer(request))


def _new_session() -> str:
    return _sign(int(time.time()) + SESSION_TTL)


def _make_challenge_id(purpose: str, challenge: bytes) -> str:
    """Stateless signed challenge (no server memory, no cookie)."""
    raw = bytes_to_base64url(json.dumps(
        {"p": purpose, "c": bytes_to_base64url(challenge), "e": int(time.time()) + CHALLENGE_TTL}).encode())
    return f"{raw}.{hmac.new(_secret(), raw.encode(), hashlib.sha256).hexdigest()}"


def _open_challenge_id(token: str, purpose: str):
    """Return challenge bytes if the id is valid, unexpired and for this purpose, else None."""
    try:
        raw, sig = token.split(".", 1)
        if not hmac.compare_digest(sig, hmac.new(_secret(), raw.encode(), hashlib.sha256).hexdigest()):
            return None
        d = json.loads(base64url_to_bytes(raw))
        if d["p"] != purpose or d["e"] < time.time():
            return None
        return base64url_to_bytes(d["c"])
    except Exception:
        return None


@app.middleware("http")
async def require_session(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path in PUBLIC or request.url.path == "/telegram/webhook" or request.url.path.startswith("/worker/"):
        return await call_next(request)
    if not _session_ok(request):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)


# Added after require_session so CORS wraps it: 401 responses still carry CORS headers.
app.add_middleware(
    CORSMiddleware, allow_origins=[ORIGIN], allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "X-Setup-Token", "X-Challenge-Id", "Authorization", "X-Worker-Token"],
)


@app.on_event("startup")
async def _start():
    await _load_remote_creds()
    asyncio.create_task(storage.retry_loop())


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/auth/me")
async def me():
    return {"ok": True}  # reached only with a valid session (see middleware)


# ---- passkey (WebAuthn) ----
_cred_cache = None  # list of {id, pk, count}; public key data only


def _creds() -> list:
    global _cred_cache
    if _cred_cache is None:
        try:
            _cred_cache = json.loads(CRED_FILE.read_text())
        except Exception:
            _cred_cache = []
    return _cred_cache


def _write_local(text: str):
    """Best-effort local cache; a read-only disk must never cause a 500."""
    try:
        CRED_FILE.parent.mkdir(parents=True, exist_ok=True)
        CRED_FILE.write_text(text)
    except OSError as e:
        log.warning("local credentials write failed: %s", type(e).__name__)


async def _load_remote_creds():
    """Restore credentials from the private store repo (survives redeploys)."""
    global _cred_cache
    try:
        text = await storage.read_file(CRED_REMOTE)
        if text:
            _cred_cache = json.loads(text)
            _write_local(text)
    except Exception as e:
        log.warning("loading remote credentials failed: %s", type(e).__name__)  # fall back to local file


async def _save_creds(creds: list):
    global _cred_cache
    _cred_cache = creds
    text = json.dumps(creds)
    _write_local(text)
    if not await storage.commit_file(CRED_REMOTE, text, "update passkey credentials", "credentials"):
        log.warning("saving credentials to store repo failed (queued locally)")


@app.post("/auth/register/options")
async def reg_options(request: Request):
    # Only the first device may register without a session; later ones need a session.
    if _creds() and not _session_ok(request):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    if os.environ.get("SETUP_TOKEN") and request.headers.get("x-setup-token") != os.environ["SETUP_TOKEN"]:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    opts = webauthn.generate_registration_options(
        rp_id=RP_ID, rp_name=RP_NAME, user_id=b"haru-owner", user_name="owner")
    out = json.loads(webauthn.options_to_json(opts))
    out["challenge_id"] = _make_challenge_id("reg", opts.challenge)
    return JSONResponse(out)


@app.post("/auth/register/verify")
async def reg_verify(request: Request):
    if _creds() and not _session_ok(request):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    if os.environ.get("SETUP_TOKEN") and request.headers.get("x-setup-token") != os.environ["SETUP_TOKEN"]:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    challenge = _open_challenge_id(request.headers.get("x-challenge-id", ""), "reg")
    if challenge is None:
        log.warning("register verify: missing/invalid/expired challenge id")
        return JSONResponse({"detail": "verification failed"}, status_code=400)
    try:
        v = webauthn.verify_registration_response(
            credential=await request.json(), expected_challenge=challenge,
            expected_rp_id=RP_ID, expected_origin=ORIGIN)
    except Exception as e:
        log.warning("register verify failed: %s: %s", type(e).__name__, e)
        return JSONResponse({"detail": "verification failed"}, status_code=400)
    creds = _creds()
    creds.append({"id": bytes_to_base64url(v.credential_id),
                  "pk": bytes_to_base64url(v.credential_public_key), "count": v.sign_count})
    await _save_creds(creds)
    return JSONResponse({"ok": True, "token": _new_session()})


@app.post("/auth/login/options")
async def login_options():
    opts = webauthn.generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(c["id"])) for c in _creds()])
    out = json.loads(webauthn.options_to_json(opts))
    out["challenge_id"] = _make_challenge_id("auth", opts.challenge)
    return JSONResponse(out)


@app.post("/auth/login/verify")
async def login_verify(request: Request):
    body = await request.json()
    cred = next((c for c in _creds() if c["id"] == body.get("id")), None)
    challenge = _open_challenge_id(request.headers.get("x-challenge-id", ""), "auth")
    if not cred or challenge is None:
        log.warning("login verify: unknown credential=%s, valid challenge=%s", cred is None, challenge is not None)
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    try:
        v = webauthn.verify_authentication_response(
            credential=body, expected_challenge=challenge,
            expected_rp_id=RP_ID, expected_origin=ORIGIN,
            credential_public_key=base64url_to_bytes(cred["pk"]), credential_current_sign_count=cred["count"])
    except Exception as e:
        log.warning("login verify failed: %s: %s", type(e).__name__, e)
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    creds = _creds()
    for c in creds:
        if c["id"] == cred["id"]:
            c["count"] = v.new_sign_count
    await _save_creds(creds)
    return JSONResponse({"ok": True, "token": _new_session()})


# ---- chat ----
MAX_MESSAGES = 200
MAX_CHARS = 200_000


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _clean_messages(raw) -> list:
    """Keep only role/content strings and cap the size (server memory stays small)."""
    out, total = [], 0
    for m in (raw or [])[-MAX_MESSAGES:]:
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant", "system"):
            continue
        content = m.get("content")
        if not isinstance(content, str):
            continue
        total += len(content)
        if total > MAX_CHARS:
            break
        item = {"role": m["role"], "content": content}
        if isinstance(m.get("model"), str):
            item["model"] = m["model"]
        if m["role"] == "user" and isinstance(m.get("images"), list):
            ids = [i for i in m["images"] if isinstance(i, str) and uploads.valid_id(i)]
            if ids:
                item["images"] = ids[: uploads.MAX_IMAGES_PER_REQUEST]
        out.append(item)
    return out


@app.post("/uploads")
async def upload(request: Request, name: str = ""):
    """Raw image bytes in the body (Content-Type image/*), name in the query. Returns {id, name, mime, size}."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > uploads.MAX_BYTES:
        return JSONResponse({"detail": "image too large"}, status_code=413)
    buf = bytearray()
    async for chunk in request.stream():
        buf += chunk
        if len(buf) > uploads.MAX_BYTES:
            return JSONResponse({"detail": "image too large"}, status_code=413)
    try:
        return await uploads.save(bytes(buf), name)
    except uploads.UploadError as e:
        return JSONResponse({"detail": e.detail}, status_code=e.status)


@app.get("/uploads/{upload_id}")
async def upload_get(upload_id: str):
    try:
        got = await uploads.load(upload_id)
    except Exception as e:
        return _store_error(e)
    if got is None:
        return JSONResponse({"detail": "not found"}, status_code=404)
    return Response(got[0], media_type=got[1], headers={"Cache-Control": "private, max-age=86400"})


@app.get("/memory")
async def memory_list():
    try:
        return {"memories": await memory.list_all()}
    except Exception as e:
        return _store_error(e)


@app.get("/memory/{mid}")
async def memory_get(mid: str):
    try:
        e = await memory.get(mid)
    except Exception as ex:
        return _store_error(ex)
    return e if e else JSONResponse({"detail": "not found"}, status_code=404)


@app.post("/memory")
async def memory_create(request: Request):
    body = await request.json()
    try:
        return await memory.create(body.get("topic"), body.get("content"))
    except memory.MemoryError_ as e:
        return JSONResponse({"detail": e.detail}, status_code=e.status)
    except Exception as e:
        return _store_error(e)


@app.put("/memory/{mid}")
async def memory_update(mid: str, request: Request):
    body = await request.json()
    try:
        e = await memory.update(mid, body.get("topic"), body.get("content"))
    except memory.MemoryError_ as ex:
        return JSONResponse({"detail": ex.detail}, status_code=ex.status)
    except Exception as ex:
        return _store_error(ex)
    return e if e else JSONResponse({"detail": "not found"}, status_code=404)


@app.delete("/memory/{mid}")
async def memory_delete(mid: str):
    """Call only after the user confirmed in the UI."""
    try:
        ok = await memory.delete(mid)
    except Exception as e:
        return _store_error(e)
    return {"ok": True} if ok else JSONResponse({"detail": "not found"}, status_code=404)


def _gh_error(e: Exception):
    if isinstance(e, connector.ConnectorError):
        return JSONResponse({"detail": e.detail}, status_code=e.status)
    return _store_error(e)


@app.get("/github/repos")
async def github_repos():
    """Repos the server token can see (read-only connector)."""
    try:
        return {"repos": await connector.repos()}
    except Exception as e:
        return _gh_error(e)


@app.get("/github/files")
async def github_files(repo: str, path: str = "", ref: str = ""):
    try:
        return {"repo": repo, "path": path, "files": await connector.list_files(repo, path, ref)}
    except Exception as e:
        return _gh_error(e)


@app.get("/github/file")
async def github_file(repo: str, path: str, ref: str = ""):
    try:
        return await connector.read_file(repo, path, ref)
    except Exception as e:
        return _gh_error(e)


def _proj_error(e: Exception):
    if isinstance(e, projects.ProjectError):
        return JSONResponse({"detail": e.detail}, status_code=e.status)
    return _store_error(e)


@app.get("/projects")
async def projects_list():
    try:
        return {"projects": await projects.list_all()}
    except Exception as e:
        return _proj_error(e)


@app.post("/projects")
async def projects_create(request: Request):
    body = await request.json()
    try:
        return await projects.create(body.get("name"), body.get("instructions", ""), body.get("files"))
    except Exception as e:
        return _proj_error(e)


@app.get("/projects/{pid}")
async def projects_get(pid: str):
    try:
        p = await projects.get(pid)
    except Exception as e:
        return _proj_error(e)
    return p if p else JSONResponse({"detail": "not found"}, status_code=404)


@app.put("/projects/{pid}")
async def projects_update(pid: str, request: Request):
    body = await request.json()
    try:
        p = await projects.update(pid, body.get("name"), body.get("instructions"), body.get("files"))
    except Exception as e:
        return _proj_error(e)
    return p if p else JSONResponse({"detail": "not found"}, status_code=404)


@app.post("/projects/{pid}/files")
async def projects_add_file(pid: str, request: Request):
    body = await request.json()
    try:
        p = await projects.add_file(pid, str(body.get("name", "")), body.get("content"))
    except Exception as e:
        return _proj_error(e)
    return p if p else JSONResponse({"detail": "not found"}, status_code=404)


@app.delete("/projects/{pid}/files/{name}")
async def projects_remove_file(pid: str, name: str):
    """Call only after the user confirmed in the UI."""
    try:
        p = await projects.remove_file(pid, name)
    except Exception as e:
        return _proj_error(e)
    return p if p else JSONResponse({"detail": "not found"}, status_code=404)


@app.delete("/projects/{pid}")
async def projects_delete(pid: str):
    """Call only after the user confirmed in the UI. The project's chats are kept."""
    try:
        ok = await projects.delete(pid)
    except Exception as e:
        return _proj_error(e)
    return {"ok": True} if ok else JSONResponse({"detail": "not found"}, status_code=404)


@app.get("/artifacts")
async def artifacts_list(chat_id: str = ""):
    try:
        return {"artifacts": await artifacts.list_all(chat_id)}
    except Exception as e:
        return _store_error(e)


@app.get("/artifacts/{aid}")
async def artifacts_get(aid: str):
    try:
        a = await artifacts.get(aid)
    except Exception as e:
        return _store_error(e)
    return a if a else JSONResponse({"detail": "not found"}, status_code=404)


@app.delete("/artifacts/{aid}")
async def artifacts_delete(aid: str):
    """Call only after the user confirmed in the UI."""
    try:
        ok = await artifacts.delete(aid)
    except Exception as e:
        return _store_error(e)
    return {"ok": True} if ok else JSONResponse({"detail": "not found"}, status_code=404)


@app.get("/usage")
async def usage_get():
    """Free-tier usage for the settings screen. No billing fields. Times are unix seconds (UTC)."""
    try:
        cx = await codex.usage()
    except Exception:
        cx = None  # GitHub unreachable: the other numbers are still useful
    return {"as_of": int(time.time()), "codex": cx, **usage.snapshot()}


@app.get("/models")
async def models():
    return {"default": "auto", "models": router.models()}


async def _chat_state(chat_id: str):
    """(chat already exists?, project the chat belongs to). One lookup per request; tests replace it."""
    return await storage.chat_exists(chat_id), await storage.chat_project_id(chat_id)


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    messages = _clean_messages(body.get("messages"))
    chat_id = body.get("chat_id") or secrets.token_hex(8)
    mode = body.get("mode", "auto")
    if not isinstance(mode, str):
        mode = "auto"
    if mode not in ("auto", "easy", "hard") and not any(m["id"] == mode for m in router.models()):
        mode = "auto"
    web = body.get("web", "auto") if body.get("web", "auto") in ("auto", "on", "off") else "auto"
    temporary = bool(body.get("temporary", False))
    effort = body.get("effort") if body.get("effort") in codex.EFFORTS else ""  # reasoning effort, Codex only
    project_id = body.get("project_id") if isinstance(body.get("project_id"), str) else ""
    if project_id and not projects.valid_id(project_id):
        project_id = ""
    # Only model-visible fields go to the providers.
    prompt = [{"role": m["role"], "content": m["content"]} for m in messages]
    attach = [(i, img) for i, m in enumerate(messages) for img in m.get("images", [])]
    attach = attach[-uploads.MAX_IMAGES_PER_REQUEST:]

    async def gen():
        nonlocal mode
        parts, model, results, gh_sources = [], None, [], []
        remembered = False
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        # Photos first: prompt[i] must still line up with messages[i] before system messages are inserted.
        if attach:
            loaded = {}
            for i, img in attach:
                got = await uploads.load(img)
                if got:
                    loaded.setdefault(i, []).append(uploads.data_uri(*got))
            if loaded:
                for i, uris in loaded.items():
                    text = prompt[i]["content"] or "이 이미지를 설명해 주세요."
                    prompt[i] = {"role": "user", "content": [{"type": "text", "text": text}] + [
                        {"type": "image_url", "image_url": {"url": u}} for u in uris]}
                mode = router.VISION_MODEL  # images are read by the vision model only
                yield _sse("notice", "사진을 읽는 중이에요.")
            else:
                yield _sse("notice", "첨부한 사진을 찾지 못했어요.")
        if not temporary:  # temporary chats neither read nor write memory
            wanted = memory.extract_request(last_user)
            if wanted:
                try:
                    e = await memory.create(wanted[:60], wanted)
                    remembered = True
                    yield _sse("notice", f"기억했어요: {e['topic']}")
                except Exception:
                    yield _sse("notice", "기억을 저장하지 못했어요.")
            mem_msg = await memory.prompt_message()
            if mem_msg:
                prompt.insert(0, mem_msg)
        chat_known, stored_pid = False, ""
        if not temporary:
            chat_known, stored_pid = await _chat_state(chat_id)
        pid = project_id or stored_pid  # a chat keeps its project
        if pid:
            try:
                proj = await projects.get(pid)
            except Exception:
                proj = None
            if proj:
                prompt.insert(0, projects.prompt_message(proj))
            else:
                pid = ""  # deleted or unreachable: chat without project context
        gh_plan = None if attach else await connector.plan(last_user)  # photos: no GitHub lookup
        if gh_plan:
            yield _sse("notice", "GitHub에서 확인하는 중이에요.")
            ctx = await connector.context_for(gh_plan)
            if ctx:
                prompt.insert(0, ctx[0])
                gh_sources = ctx[1]
        if search.needs_search(messages, web):
            yield _sse("notice", "웹에서 검색하는 중이에요.")
            results = await search.search(last_user)
            if results:
                prompt.insert(0, search.context_message(results))
        async for kind, text in router.route(prompt, mode, effort):
            if kind == "model":
                model = text  # internal: reported in the done event only
            elif kind == "delta":
                parts.append(text)
                yield _sse("delta", text)
            else:
                yield _sse("notice", text)
        if parts and results:
            tail = search.sources_text(results)
            parts.append(tail)
            yield _sse("delta", tail)
        saved, title, cid, new_arts = False, None, chat_id, []
        if parts and not temporary:  # nothing to save if no model answered or the chat is temporary
            answer = "".join(parts)
            first_user = next((m["content"] for m in messages if m["role"] == "user"), "")

            async def no_title():
                return None

            got = await asyncio.gather(
                llm.make_title(first_user, answer) if not chat_known else no_title(),  # title only after the first answer
                no_title() if remembered else memory.suggest(last_user, answer),
                artifacts.save(chat_id, answer),
                return_exceptions=True)
            new_title = got[0] if isinstance(got[0], str) else ""
            if not isinstance(got[1], BaseException) and got[1]:
                yield _sse("notice", "기억 업데이트됨")
            if not isinstance(got[2], BaseException):
                new_arts = [{"id": a["id"], "title": a["title"], "language": a["language"]} for a in got[2][0]]
            full = messages + [{"role": "assistant", "content": answer, "model": model}]
            saved, meta = await storage.save_chat(chat_id, {"messages": full}, title=new_title, project_id=pid)
            title, cid = meta["title"], meta["id"]
        yield _sse("done", {"chat_id": cid, "saved": saved, "model": model, "title": title,
                            "temporary": temporary, "project_id": pid or None, "artifacts": new_arts,
                            "sources": [{"title": r["title"], "url": r["url"]} for r in results] + gh_sources})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _store_error(e: Exception):
    log.warning("store request failed: %s", type(e).__name__)
    return JSONResponse({"detail": "storage unavailable"}, status_code=502)


@app.get("/chats")
async def chats(q: str = "", limit: int = 100, project_id: str = ""):
    try:
        return {"chats": await storage.list_chats(q, max(1, min(limit, 500)), project_id)}
    except Exception as e:
        return _store_error(e)


@app.get("/chats/{chat_id}")
async def chat_detail(chat_id: str):
    try:
        d = await storage.get_chat(chat_id)
    except Exception as e:
        return _store_error(e)
    return d if d is not None else JSONResponse({"detail": "not found"}, status_code=404)


@app.post("/chats/{chat_id}/rename")
async def chat_rename(chat_id: str, request: Request):
    title = str((await request.json()).get("title", ""))
    try:
        ok = await storage.rename_chat(chat_id, title)
    except Exception as e:
        return _store_error(e)
    return {"ok": True} if ok else JSONResponse({"detail": "not found"}, status_code=404)


@app.delete("/chats/{chat_id}")
async def chat_delete(chat_id: str):
    try:
        ok = await storage.delete_chat(chat_id)
    except Exception as e:
        return _store_error(e)
    return {"ok": True} if ok else JSONResponse({"detail": "not found"}, status_code=404)


def _worker_ok(request: Request):
    return task_queue.worker_authorized(request.headers.get("x-worker-token", ""))


@app.post("/tasks")
async def task_create(request: Request):
    body = await request.json()
    content = body.get("content")
    mode = body.get("mode", "auto")
    if not isinstance(content, str) or not content.strip():
        return JSONResponse({"detail": "content required"}, status_code=400)
    try:
        task = await task_queue.create(content, mode, body.get("conversation_id", body.get("chat_id", "")))
    except ValueError as e:
        return JSONResponse({"detail": str(e)}, status_code=400)
    return {"id": task["id"], "status": task["status"]}


@app.get("/tasks/{task_id}/events")
async def task_events(task_id: str):
    if task_id not in task_queue.TASKS:
        return JSONResponse({"detail": "not found"}, status_code=404)
    async def stream():
        cursor = 0
        while True:
            events = task_queue.EVENTS.get(task_id, [])
            while cursor < len(events):
                item = events[cursor]
                yield f"id: {item['id']}\nevent: {item['event']}\ndata: {json.dumps(item['data'], ensure_ascii=False)}\n\n"
                cursor += 1
            if task_queue.TASKS[task_id]["status"] in ("done", "failed", "stopped"):
                return
            await asyncio.sleep(0.5)
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.post("/tasks/{task_id}/permission")
async def task_permission(task_id: str, request: Request):
    body = await request.json()
    decision = body.get("decision")
    if decision not in ("allow", "always", "deny"):
        return JSONResponse({"detail": "decision must be allow, always, or deny"}, status_code=400)
    task = task_queue.TASKS.get(task_id)
    if not task:
        return JSONResponse({"detail": "not found"}, status_code=404)
    task["permissions"].append(decision)
    task_queue.add_event(task_id, "permission", {"decision": decision, "task_id": task_id})
    return {"ok": True}


@app.post("/tasks/{task_id}/stop")
async def task_stop(task_id: str):
    task = task_queue.TASKS.get(task_id)
    if not task:
        return JSONResponse({"detail": "not found"}, status_code=404)
    task.update(status="stopped")
    task_queue.add_event(task_id, "stopped", {})
    return {"ok": True}


@app.post("/tasks/{task_id}/message")
async def task_message(task_id: str, request: Request):
    body = await request.json()
    task = task_queue.TASKS.get(task_id)
    if not task:
        return JSONResponse({"detail": "not found"}, status_code=404)
    task["messages"].append(str(body.get("content", "")))
    task_queue.add_event(task_id, "message", {"content": str(body.get("content", ""))})
    return {"ok": True}


@app.post("/worker/claim")
async def worker_claim(request: Request):
    if not _worker_ok(request): return JSONResponse({"detail": "unauthorized"}, status_code=401)
    body = await request.json()
    return {"task": await task_queue.claim(str(body.get("worker_id", "worker")))}


@app.post("/worker/plan")
async def worker_plan(request: Request):
    if not _worker_ok(request): return JSONResponse({"detail": "unauthorized"}, status_code=401)
    body = await request.json()
    task = task_queue.TASKS.get(body.get("task_id"))
    if not task: return JSONResponse({"detail": "not found"}, status_code=404)
    prompt = ("Plan one safe, read-only or workspace-local shell command to fulfill the task. "
              "Never read secrets or .env files. Never delete, send data externally, push, deploy, or pay. "
              "Return only JSON with keys command and summary. The command runs inside the task workspace.\n\n"
              f"Task: {task['content']}\nWorkspace entries: {json.dumps(body.get('entries', []), ensure_ascii=False)}")
    parts, model = [], None
    async for kind, value in router.route([{"role": "user", "content": prompt}], "auto"):
        if kind == "model": model = value
        elif kind == "delta": parts.append(value)
    if not parts:
        return JSONResponse({"detail": "model unavailable"}, status_code=503)
    try:
        plan = json.loads("".join(parts).strip().removeprefix("```json").removesuffix("```").strip())
    except (ValueError, TypeError):
        return JSONResponse({"detail": "model returned an invalid plan"}, status_code=502)
    if not isinstance(plan.get("command"), str) or not isinstance(plan.get("summary"), str):
        return JSONResponse({"detail": "model returned an invalid plan"}, status_code=502)
    return {"command": plan["command"], "summary": plan["summary"], "model": model}


@app.post("/worker/heartbeat")
async def worker_heartbeat(request: Request):
    if not _worker_ok(request): return JSONResponse({"detail": "unauthorized"}, status_code=401)
    body = await request.json()
    ok = await task_queue.heartbeat(body.get("task_id"), body.get("worker_id"), body.get("checkpoint"))
    return {"ok": ok}


@app.get("/worker/events")
async def worker_events(request: Request, task_id: str):
    if not _worker_ok(request): return JSONResponse({"detail": "unauthorized"}, status_code=401)
    task = task_queue.TASKS.get(task_id)
    if not task: return JSONResponse({"detail": "not found"}, status_code=404)
    permission = task["permissions"].popleft() if task["permissions"] else None
    return {"messages": list(task["messages"]), "permission": permission, "stopped": task["status"] == "stopped"}


@app.post("/worker/permission")
async def worker_permission(request: Request):
    if not _worker_ok(request): return JSONResponse({"detail": "unauthorized"}, status_code=401)
    body = await request.json()
    task = task_queue.TASKS.get(body.get("task_id"))
    if not task: return JSONResponse({"detail": "not found"}, status_code=404)
    task_queue.publish(task["id"], "permission_required", {"command": body.get("command", "")})
    while task["status"] == "running":
        if task["permissions"]:
            return {"decision": task["permissions"].popleft()}
        await asyncio.sleep(0.5)
    return {"decision": "deny"}


@app.post("/worker/event")
async def worker_event(request: Request):
    if not _worker_ok(request): return JSONResponse({"detail": "unauthorized"}, status_code=401)
    body = await request.json()
    if not task_queue.publish(body.get("task_id"), body.get("event"), body.get("data", {})):
        return JSONResponse({"detail": "not found"}, status_code=404)
    return {"ok": True}


@app.post("/worker/done")
async def worker_done(request: Request):
    if not _worker_ok(request): return JSONResponse({"detail": "unauthorized"}, status_code=401)
    body = await request.json()
    task = task_queue.TASKS.get(body.get("task_id"))
    if not task: return JSONResponse({"detail": "not found"}, status_code=404)
    task.update(status="failed" if body.get("error") else "done")
    task_queue.add_event(task["id"], task["status"], {"result": body.get("result", ""), "error": body.get("error", "")})
    return {"ok": True}


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
    if not secret or not hmac.compare_digest(request.headers.get("x-telegram-bot-api-secret-token", ""), secret):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    body = await request.json()
    if str(body.get("message", {}).get("chat", {}).get("id", "")) != os.environ.get("TELEGRAM_CHAT_ID", ""):
        return {"ok": True}
    callback = body.get("callback_query")
    if callback:
        task_id, decision = str(callback.get("data", "")).split(":", 1)
        task = task_queue.TASKS.get(task_id)
        if task and decision in ("allow", "always", "deny"):
            task["permissions"].append(decision)
            task_queue.add_event(task_id, "permission", {"decision": decision})
    return {"ok": True}
