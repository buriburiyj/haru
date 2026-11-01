import asyncio
import base64
import hashlib
import hmac
import json
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

import router
import storage

ORIGIN = "https://buriburiyj.github.io"
RP_ID = "buriburiyj.github.io"
RP_NAME = "Haru"
COOKIE = "haru_session"
SESSION_TTL = 60 * 60 * 24 * 30
CRED_FILE = Path(os.environ.get("CRED_FILE", Path(__file__).parent / "credentials.json"))
PUBLIC = {"/health", "/auth/register/options", "/auth/register/verify", "/auth/login/options", "/auth/login/verify"}

app = FastAPI()
app.add_middleware(
    CORSMiddleware, allow_origins=[ORIGIN], allow_credentials=True,
    allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
)
_challenges: dict = {}  # purpose -> challenge bytes (single user)


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


@app.middleware("http")
async def require_session(request: Request, call_next):
    if request.method == "OPTIONS" or request.url.path in PUBLIC:
        return await call_next(request)
    if not _valid(request.cookies.get(COOKIE, "")):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)


@app.on_event("startup")
async def _start():
    asyncio.create_task(storage.retry_loop())


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/auth/me")
async def me():
    return {"ok": True}  # reached only with a valid session (see middleware)


# ---- passkey (WebAuthn) ----
def _creds() -> list:
    try:
        return json.loads(CRED_FILE.read_text())
    except Exception:
        return []


def _set_session(resp: Response):
    resp.set_cookie(COOKIE, _sign(int(time.time()) + SESSION_TTL), max_age=SESSION_TTL,
                    httponly=True, secure=True, samesite="none")


@app.post("/auth/register/options")
async def reg_options(request: Request):
    # Only the first device may register without a session; later ones need a session.
    if _creds() and not _valid(request.cookies.get(COOKIE, "")):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    if os.environ.get("SETUP_TOKEN") and request.headers.get("x-setup-token") != os.environ["SETUP_TOKEN"]:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    opts = webauthn.generate_registration_options(
        rp_id=RP_ID, rp_name=RP_NAME, user_id=b"haru-owner", user_name="owner")
    _challenges["reg"] = opts.challenge
    return Response(webauthn.options_to_json(opts), media_type="application/json")


@app.post("/auth/register/verify")
async def reg_verify(request: Request):
    if _creds() and not _valid(request.cookies.get(COOKIE, "")):
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    if os.environ.get("SETUP_TOKEN") and request.headers.get("x-setup-token") != os.environ["SETUP_TOKEN"]:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    try:
        v = webauthn.verify_registration_response(
            credential=await request.json(), expected_challenge=_challenges.pop("reg"),
            expected_rp_id=RP_ID, expected_origin=ORIGIN)
    except Exception:
        return JSONResponse({"detail": "verification failed"}, status_code=400)
    creds = _creds()
    creds.append({"id": bytes_to_base64url(v.credential_id),
                  "pk": bytes_to_base64url(v.credential_public_key), "count": v.sign_count})
    CRED_FILE.write_text(json.dumps(creds))
    resp = JSONResponse({"ok": True})
    _set_session(resp)
    return resp


@app.post("/auth/login/options")
async def login_options():
    opts = webauthn.generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(c["id"])) for c in _creds()])
    _challenges["auth"] = opts.challenge
    return Response(webauthn.options_to_json(opts), media_type="application/json")


@app.post("/auth/login/verify")
async def login_verify(request: Request):
    body = await request.json()
    cred = next((c for c in _creds() if c["id"] == body.get("id")), None)
    if not cred or "auth" not in _challenges:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    try:
        v = webauthn.verify_authentication_response(
            credential=body, expected_challenge=_challenges.pop("auth"),
            expected_rp_id=RP_ID, expected_origin=ORIGIN,
            credential_public_key=base64url_to_bytes(cred["pk"]), credential_current_sign_count=cred["count"])
    except Exception:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    creds = _creds()
    for c in creds:
        if c["id"] == cred["id"]:
            c["count"] = v.new_sign_count
    CRED_FILE.write_text(json.dumps(creds))
    resp = JSONResponse({"ok": True})
    _set_session(resp)
    return resp


# ---- chat ----
def _sse(event: str, data: str) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    messages = body.get("messages") or []
    chat_id = body.get("chat_id") or secrets.token_hex(8)
    mode = body.get("mode", "auto")
    if mode not in ("auto", "easy", "hard"):
        mode = "auto"

    async def gen():
        parts = []
        async for kind, text in router.route(messages, mode):
            if kind == "delta":
                parts.append(text)
            yield _sse(kind, text)
        full = messages + [{"role": "assistant", "content": "".join(parts)}]
        saved = await storage.save_chat(chat_id, {"id": chat_id, "messages": full})
        yield _sse("done", json.dumps({"chat_id": chat_id, "saved": saved}))

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
