"""Model router: Groq classify -> Codex (placeholder) -> NVIDIA fallback chain."""
import json
import os
import asyncio
import httpx

import codex
import usage

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")
CODEX_MODELS = ["gpt-6-luna", "gpt-5.6-terra", "gpt-5.6-luna"]  # provisional order
NVIDIA_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b",
    "mistralai/mistral-large-4-1t-a52b",
    "deepseek-ai/deepseek-v4.1-flash",
]


def _catalog() -> list:
    out = [{"id": GROQ_MODEL, "label": GROQ_MODEL.split("/")[-1], "provider": "groq"}]
    out += [{"id": m, "label": m, "provider": "codex"} for m in CODEX_MODELS]
    out += [{"id": m, "label": m.split("/")[-1], "provider": "nvidia"} for m in NVIDIA_MODELS]
    return out


def models() -> list:
    """Models for the UI picker: automatic first, then Groq, the 3 Codex models, the NVIDIA models."""
    return [{"id": "auto", "label": "자동", "provider": "auto"}] + _catalog()


VISION_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"  # used when a message has images; not in the picker


def _provider(model: str):
    if model == VISION_MODEL:
        return "nvidia"
    for m in _catalog():  # "auto" is not a model
        if m["id"] == model:
            return m["provider"]
    return None


def _extra(model: str) -> dict:
    # gpt-oss on Groq is a reasoning model: keep it short and fast.
    return {"reasoning_effort": "low"} if "gpt-oss" in model else {}


class QuotaError(Exception):
    pass


class RateLimited(QuotaError):
    """HTTP 429. `retry_after` is how long the provider asked us to wait (seconds, capped)."""

    def __init__(self, retry_after: float = 2.0):
        super().__init__("429")
        self.retry_after = retry_after


RETRY_CAP_SECONDS = 6.0


def _retry_after(r) -> float:
    try:
        return max(1.0, min(float(r.headers.get("retry-after", 2)), RETRY_CAP_SECONDS))
    except (TypeError, ValueError):
        return 2.0


def _key(name: str) -> str:
    v = os.environ.get(name, "")
    if not v:
        raise QuotaError(f"{name} not set")
    return v


async def classify(client: httpx.AsyncClient, messages: list) -> str:
    """Return 'easy' or 'hard'. Defaults to 'hard' on any failure."""
    try:
        last = messages[-1]["content"]
        last = last if isinstance(last, str) else " ".join(p.get("text", "") for p in last if isinstance(p, dict))
        last = last[:2000]
        usage.count("groq")
        r = await client.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {_key('GROQ_API_KEY')}"},
            json={
                "model": GROQ_MODEL,
                "max_tokens": 200,
                **_extra(GROQ_MODEL),
                "messages": [
                    {"role": "system", "content": "Answer one word: easy (chitchat, short, summary) or hard (coding, planning, long reasoning)."},
                    {"role": "user", "content": last},
                ],
            },
            timeout=15,
        )
        r.raise_for_status()
        out = r.json()["choices"][0]["message"]["content"].lower()
        return "easy" if "easy" in out else "hard"
    except Exception:
        return "hard"


async def _stream_openai(client, url, key_name, model, messages):
    """Yield text deltas from an OpenAI-compatible streaming endpoint."""
    provider = "groq" if key_name.startswith("GROQ") else "nvidia"
    usage.count(provider)
    async with client.stream(
        "POST", url,
        headers={"Authorization": f"Bearer {_key(key_name)}"},
        json={"model": model, "messages": messages, "stream": True, **_extra(model)},
        timeout=httpx.Timeout(60, read=60),
    ) as r:
        if r.status_code == 429:
            usage.count(provider, rate_limited=True)
            raise RateLimited(_retry_after(r))
        if r.status_code >= 400:
            raise QuotaError(f"http {r.status_code}")
        async for line in r.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                return
            try:
                delta = json.loads(data)["choices"][0]["delta"].get("content")
            except (ValueError, KeyError, IndexError):
                continue
            if delta:
                yield delta


async def route(messages: list, mode: str = "auto", effort: str = ""):
    """Async generator of (kind, value).
    kind: 'model' (id of the model that is answering), 'delta' (answer text),
    'notice' (user-facing status, e.g. all models unavailable).
    `effort` only affects Codex; Groq and NVIDIA ignore it."""
    async with httpx.AsyncClient() as client:
        direct = _provider(mode)
        if direct:
            chain = [(direct, [mode] if direct == "codex" else mode)]  # user picked a model: no fallback
        else:
            level = await classify(client, messages) if mode == "auto" else mode
            nvidia = [("nvidia", m) for m in NVIDIA_MODELS]
            if level == "easy":
                chain = [("groq", GROQ_MODEL)] + nvidia
            else:
                chain = [("codex", CODEX_MODELS)] + nvidia  # one Actions run tries the 3 models in order
        for prov, model in chain:
            if prov == "codex":
                try:
                    async for kind, value in codex.run(messages, model, effort):
                        yield kind, value
                    return
                except (codex.CodexUnavailable, httpx.HTTPError) as e:
                    codex.log.warning("codex unavailable: %s", e)
                    if len(chain) > 1:
                        yield "notice", "Codex를 쓸 수 없어서 다른 모델로 답해요."
                    continue
            started = False
            for attempt in (1, 2):  # a 429 is retried once after the wait the provider asked for
                try:
                    if prov == "groq":
                        gen = _stream_openai(client, GROQ_URL, "GROQ_API_KEY", model, messages)
                    else:
                        gen = _stream_openai(client, NVIDIA_URL, "NVIDIA_API_KEY", model, messages)
                    async for d in gen:
                        if not started:
                            started = True
                            yield "model", model
                        yield "delta", d
                    return
                except RateLimited as e:
                    if started:
                        yield "notice", "Stream interrupted"
                        return
                    if attempt == 1:
                        yield "notice", "요청이 몰려서 잠시 기다린 뒤 다시 시도해요."
                        await asyncio.sleep(e.retry_after)
                        continue
                    yield "notice", "요청이 많아서 다른 모델로 답해요."
                    break
                except (QuotaError, httpx.HTTPError):
                    if started:
                        yield "notice", "Stream interrupted"
                        return
                    await asyncio.sleep(0.5)
                    break
        yield "notice", "All models unavailable"
