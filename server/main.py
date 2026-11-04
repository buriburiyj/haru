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

import codex
import connector
import memory
import router
import search
import usage
import storage
import uploads

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
    if request.method == "OPTIONS" or request.url.path in PUBLIC:
        return await call_next(request)
    if not _session_ok(request):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)


# Added after require_session so CORS wraps it: 401 responses still carry CORS headers.
app.add_middleware(
    CORSMiddleware, allow_origins=[ORIGIN], allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type", "X-Setup-Token", "X-Challenge-Id", "Authorization"],
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
    # Only model-visible fields go to the providers.
    prompt = [{"role": m["role"], "content": m["content"]} for m in messages]
    attach = [(i, img) for i, m in enumerate(messages) for img in m.get("images", [])]
    attach = attach[-uploads.MAX_IMAGES_PER_REQUEST:]

    async def gen():
        nonlocal mode
        parts, model, results, gh_sources = [], None, [], []
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
                    yield _sse("notice", f"기억했어요: {e['topic']}")
                except Exception:
                    yield _sse("notice", "기억을 저장하지 못했어요.")
            mem_msg = await memory.prompt_message()
            if mem_msg:
                prompt.insert(0, mem_msg)
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
        async for kind, text in router.route(prompt, mode):
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
        saved, title, cid = False, None, chat_id
        if parts and not temporary:  # nothing to save if no model answered or the chat is temporary
            full = messages + [{"role": "assistant", "content": "".join(parts), "model": model}]
            saved, meta = await storage.save_chat(chat_id, {"messages": full})
            title, cid = meta["title"], meta["id"]
        yield _sse("done", {"chat_id": cid, "saved": saved, "model": model, "title": title,
                            "temporary": temporary,
                            "sources": [{"title": r["title"], "url": r["url"]} for r in results] + gh_sources})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _store_error(e: Exception):
    log.warning("store request failed: %s", type(e).__name__)
    return JSONResponse({"detail": "storage unavailable"}, status_code=502)


@app.get("/chats")
async def chats(q: str = "", limit: int = 100):
    try:
        return {"chats": await storage.list_chats(q, max(1, min(limit, 500)))}
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
