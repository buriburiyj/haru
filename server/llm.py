"""Small helper calls to Groq (titles, memory suggestions). Never raises; returns None on any failure."""
import json
import os
import re

import httpx

import router
import usage


async def ask(system: str, user: str, max_tokens: int = 200, timeout: float = 8.0):
    if os.environ.get("HARU_DISABLE_LLM") or not os.environ.get("GROQ_API_KEY"):
        return None
    try:
        usage.count("groq")
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(
                router.GROQ_URL,
                headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
                json={"model": router.GROQ_MODEL, "max_tokens": max_tokens, **router._extra(router.GROQ_MODEL),
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        if r.status_code == 429:
            usage.count("groq", rate_limited=True)
            return None
        r.raise_for_status()
        return (r.json()["choices"][0]["message"].get("content") or "").strip() or None
    except Exception:
        return None


def parse_json(text):
    """First {...} object in `text` as a dict, or None."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        d = json.loads(m.group(0)) if m else None
    except ValueError:
        return None
    return d if isinstance(d, dict) else None


TITLE_SYSTEM = ("Write a very short title (at most 6 words, no quotes, no trailing punctuation) for this "
                "conversation, in the same language as the user's message. Reply with the title only.")


async def make_title(user_text: str, answer: str):
    """A short chat title, or None (the caller then falls back to the first words of the question)."""
    out = await ask(TITLE_SYSTEM, f"User: {user_text[:500]}\nAssistant: {answer[:500]}", max_tokens=120)
    if not out:
        return None
    t = out.splitlines()[0].strip().strip("\"'`“”‘’「」").rstrip(".。!?")
    return t[:40] if t else None
