"""Hard questions -> Codex through a GitHub Actions run in the private store repo.

Flow: commit the request to .agent/jobs/<id>.json, dispatch the workflow, poll for
.agent/jobs/<id>.out.json, stream the text as deltas, then delete both job files.
One run tries the models in order (a new run per model would triple the Actions minutes).
Memory use is a few strings per request; only one run is allowed at a time.
"""
import asyncio
import base64
import calendar
import json
import logging
import math
import os
import re
import secrets
import time

import httpx

import storage

log = logging.getLogger("uvicorn.error")

WORKFLOW = os.environ.get("CODEX_WORKFLOW", "codex-chat.yml")
MONTHLY_LIMIT_MIN = int(os.environ.get("CODEX_MONTHLY_MINUTES", "1500"))  # free plan has 2000
TOTAL_TIMEOUT = int(os.environ.get("CODEX_TIMEOUT", "300"))
START_TIMEOUT = int(os.environ.get("CODEX_START_TIMEOUT", "90"))
POLL_SECONDS = 3
NOTICE_SECONDS = 15
CHUNK = 400
JOBS_DIR = ".agent/jobs"
USAGE_PATH = ".agent/usage.json"

_lock = asyncio.Semaphore(1)
_disabled_until = 0.0  # circuit breaker after a permission/setup error
_usage = None  # {"month": "YYYY-MM", "minutes": int, "runs": int}


class CodexUnavailable(Exception):
    pass


def build_prompt(messages: list) -> str:
    lines = ["You are Haru, a helpful assistant. Answer the last user message. Reply in the user's language.", ""]
    for m in messages:
        who = {"user": "User", "assistant": "Assistant", "system": "System"}.get(m["role"], "User")
        lines.append(f"{who}: {m['content']}")
    lines.append("Assistant:")
    return "\n".join(lines)


def _month() -> str:
    return time.strftime("%Y-%m", time.gmtime())


async def _load_usage():
    global _usage
    if _usage is None:
        try:
            text = await storage.read_file(USAGE_PATH)
            _usage = json.loads(text) if text else {}
        except Exception:
            _usage = {}
    if _usage.get("month") != _month():
        _usage = {"month": _month(), "minutes": 0, "runs": 0}
    return _usage


async def usage() -> dict:
    """This month's Actions usage. `resets_at` is the start of next month (UTC), unix seconds."""
    u = await _load_usage()
    t = time.gmtime()
    nxt = calendar.timegm((t.tm_year + (t.tm_mon == 12), t.tm_mon % 12 + 1, 1, 0, 0, 0))
    return {"minutes_used": u["minutes"], "minutes_limit": MONTHLY_LIMIT_MIN, "runs": u["runs"], "resets_at": nxt}


async def _add_usage(seconds: float):
    u = await _load_usage()
    u["minutes"] += max(1, math.ceil(seconds / 60))
    u["runs"] += 1
    await storage.commit_file(USAGE_PATH, json.dumps(u), "codex usage", "usage")


def _gh(client: httpx.AsyncClient):
    base = f"{storage.API}/repos/{storage.OWNER}/{storage.REPO}"
    return base, storage._headers()


async def _dispatch(client, job: str):
    base, h = _gh(client)
    r = await client.post(f"{base}/actions/workflows/{WORKFLOW}/dispatches", headers=h,
                          json={"ref": storage.BRANCH, "inputs": {"job": job}})
    if r.status_code in (401, 403, 404, 422):
        raise CodexUnavailable(f"dispatch http {r.status_code}")
    r.raise_for_status()


async def _read_result(client, job: str):
    base, h = _gh(client)
    r = await client.get(f"{base}/contents/{JOBS_DIR}/{job}.out.json", headers=h)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return json.loads(base64.b64decode(r.json()["content"]).decode())


async def _run_state(client, since: float):
    """Return 'none', 'active' or 'failed' for the newest dispatch run created after `since`."""
    base, h = _gh(client)
    r = await client.get(f"{base}/actions/workflows/{WORKFLOW}/runs", headers=h,
                         params={"event": "workflow_dispatch", "per_page": 5})
    r.raise_for_status()
    for run in r.json().get("workflow_runs", []):
        created = calendar.timegm(time.strptime(run["created_at"], "%Y-%m-%dT%H:%M:%SZ"))
        if created >= since - 5:
            if run["status"] == "completed" and run["conclusion"] not in ("success",):
                return "failed"
            return "active"
    return "none"


async def _cleanup(job: str):
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            await storage._commit_files(
                c, {f"{JOBS_DIR}/{job}.json": None, f"{JOBS_DIR}/{job}.out.json": None}, f"cleanup {job}")
    except Exception as e:
        log.warning("codex job cleanup failed: %s", type(e).__name__)


def _chunks(text: str):
    for i in range(0, len(text), CHUNK):
        yield text[i:i + CHUNK]


EFFORTS = ("low", "medium", "high")


async def run(messages: list, models: list, effort: str = ""):
    """Async generator of ('notice'|'model'|'delta', value). Raises CodexUnavailable if no model answered.
    `effort` (low|medium|high) becomes Codex's reasoning effort; empty keeps Codex's default."""
    global _disabled_until
    if time.time() < _disabled_until:
        raise CodexUnavailable("temporarily disabled")
    if not os.environ.get("GITHUB_TOKEN"):
        raise CodexUnavailable("no token")
    u = await _load_usage()
    if u["minutes"] >= MONTHLY_LIMIT_MIN:
        yield "notice", "이번 달 Codex 사용 한도에 가까워서 다른 모델로 답해요."
        raise CodexUnavailable("monthly budget")
    if _lock.locked():
        raise CodexUnavailable("busy")  # another Codex run is active; do not queue more Actions minutes
    async with _lock:
        job = secrets.token_hex(6)
        assert re.fullmatch(r"[0-9a-f]{12}", job)
        started = time.time()
        try:
            payload = {"prompt": build_prompt(messages), "models": models}
            if effort in EFFORTS:
                payload["effort"] = effort
            req = json.dumps(payload, ensure_ascii=False)
            if not await storage.commit_file(f"{JOBS_DIR}/{job}.json", req, f"codex job {job}", f"job-{job}"):
                raise CodexUnavailable("could not write job")
            async with httpx.AsyncClient(timeout=20) as c:
                try:
                    await _dispatch(c, job)
                except CodexUnavailable:
                    _disabled_until = time.time() + 600  # setup problem: stop trying for 10 minutes
                    raise
                yield "notice", "고급 모델(Codex)을 준비하는 중이에요. 시작까지 30초~1분 걸려요."
                last_notice, last_state = time.time(), 0.0
                while True:
                    await asyncio.sleep(POLL_SECONDS)
                    elapsed = time.time() - started
                    result = await _read_result(c, job)
                    if result is not None:
                        break
                    if elapsed > TOTAL_TIMEOUT:
                        raise CodexUnavailable("timeout")
                    if time.time() - last_state >= 12:
                        last_state = time.time()
                        state = await _run_state(c, started)
                        if state == "failed" or (state == "none" and elapsed > START_TIMEOUT):
                            raise CodexUnavailable(f"run {state}")
                    if time.time() - last_notice >= NOTICE_SECONDS:
                        last_notice = time.time()
                        yield "notice", f"Codex가 작업 중이에요 ({int(elapsed)}초)"
            await _add_usage(time.time() - started)
            if not result.get("ok") or not result.get("text"):
                raise CodexUnavailable("all models failed")
            yield "model", result["model"]
            for part in _chunks(result["text"]):
                yield "delta", part
        finally:
            asyncio.ensure_future(_cleanup(job))
