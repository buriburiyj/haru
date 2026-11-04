"""Call counters for the free API tiers (Groq, NVIDIA). In memory, mirrored to a local file so a plain
restart keeps today's numbers. Counters reset at 00:00 UTC. No billing fields on purpose."""
import json
import os
import time
from pathlib import Path

USAGE_FILE = Path(os.environ.get("USAGE_FILE", "/tmp/haru_usage.json"))
_state = None  # {"day": "YYYY-MM-DD", "groq": {"calls": n, "rate_limited": n}, "nvidia": {...}}


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _next_midnight_utc() -> int:
    now = time.time()
    return int(now - now % 86400 + 86400)


def _fresh() -> dict:
    return {"day": _today(), "groq": {"calls": 0, "rate_limited": 0}, "nvidia": {"calls": 0, "rate_limited": 0}}


def _load() -> dict:
    global _state
    if _state is None:
        try:
            _state = json.loads(USAGE_FILE.read_text())
        except Exception:
            _state = _fresh()
    if _state.get("day") != _today():
        _state = _fresh()
    return _state


def count(provider: str, rate_limited: bool = False):
    """Record one request to `provider` ('groq' or 'nvidia')."""
    s = _load()
    if provider not in ("groq", "nvidia"):
        return
    if rate_limited:
        s[provider]["rate_limited"] += 1
    else:
        s[provider]["calls"] += 1
    try:
        USAGE_FILE.write_text(json.dumps(s))
    except OSError:
        pass  # best effort


def snapshot() -> dict:
    s = _load()
    reset = _next_midnight_utc()
    return {p: {"calls_today": s[p]["calls"], "rate_limited_today": s[p]["rate_limited"], "resets_at": reset}
            for p in ("groq", "nvidia")}
