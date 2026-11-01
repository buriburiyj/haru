"""Model router: Groq classify -> Codex (placeholder) -> NVIDIA fallback chain."""
import json
import os
import asyncio
import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
CODEX_MODELS = ["gpt-6-luna", "gpt-5.6-terra", "gpt-5.6-luna"]  # provisional order
NVIDIA_MODELS = [
    "nvidia/nemotron-3-ultra-550b-a55b",
    "mistralai/mistral-large-4-1t-a52b",
    "deepseek-ai/deepseek-v4.1-flash",
]


class QuotaError(Exception):
    pass


def _key(name: str) -> str:
    v = os.environ.get(name, "")
    if not v:
        raise QuotaError(f"{name} not set")
    return v


async def classify(client: httpx.AsyncClient, messages: list) -> str:
    """Return 'easy' or 'hard'. Defaults to 'hard' on any failure."""
    try:
        last = messages[-1]["content"][:2000]
        r = await client.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {_key('GROQ_API_KEY')}"},
            json={
                "model": GROQ_MODEL,
                "max_tokens": 3,
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
    async with client.stream(
        "POST", url,
        headers={"Authorization": f"Bearer {_key(key_name)}"},
        json={"model": model, "messages": messages, "stream": True},
        timeout=httpx.Timeout(60, read=60),
    ) as r:
        if r.status_code == 429:
            raise QuotaError("429")
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


async def _stream_codex(client, model, messages):
    # TODO: Codex transport is decided after the Stage 0 exam.
    raise QuotaError("codex not implemented")
    yield ""  # pragma: no cover


async def route(messages: list, mode: str = "auto"):
    """Async generator of (kind, text); kind is 'notice' or 'delta'."""
    async with httpx.AsyncClient() as client:
        level = await classify(client, messages) if mode == "auto" else mode
        chain = []
        if level == "easy":
            chain.append(("groq", GROQ_MODEL))
        else:
            chain += [("codex", m) for m in CODEX_MODELS]
            chain += [("nvidia", m) for m in NVIDIA_MODELS]
        for i, (prov, model) in enumerate(chain):
            if i:
                yield "notice", f"Switching to {model}"
            started = False
            try:
                if prov == "groq":
                    gen = _stream_openai(client, GROQ_URL, "GROQ_API_KEY", model, messages)
                elif prov == "nvidia":
                    gen = _stream_openai(client, NVIDIA_URL, "NVIDIA_API_KEY", model, messages)
                else:
                    gen = _stream_codex(client, model, messages)
                async for d in gen:
                    started = True
                    yield "delta", d
                return
            except (QuotaError, httpx.HTTPError):
                if started:
                    yield "notice", "Stream interrupted"
                    return
                await asyncio.sleep(0.5)
        yield "notice", "All models unavailable"
