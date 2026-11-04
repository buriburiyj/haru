"""Free web search through DuckDuckGo's HTML endpoint (no key, no cost)."""
import html
import re
import time
from urllib.parse import parse_qs, unquote, urlparse

import httpx

DDG_URL = "https://html.duckduckgo.com/html/"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
MAX_RESULTS = 5

_NEEDS = re.compile(
    r"\b(latest|news|today|tonight|current|currently|price|prices|weather|score|scores|recent|recently|now|202\d)\b"
    r"|최신|오늘|지금|현재|뉴스|날씨|가격|시세|주가|환율|요즘|최근|검색|찾아",
    re.IGNORECASE,
)
_BLOCK = re.compile(r'class="result__a"\s+href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=class="result__a"|\Z)', re.S)
_SNIPPET = re.compile(r'class="result__snippet"[^>]*>(.*?)</a>', re.S)
_TAGS = re.compile(r"<[^>]+>")


def needs_search(messages: list, web: str = "auto") -> bool:
    """web: 'on' always, 'off' never, 'auto' when the last user message looks time-sensitive."""
    if web == "on":
        return True
    if web == "off":
        return False
    for m in reversed(messages):
        if m.get("role") == "user":
            return bool(_NEEDS.search(m.get("content", "")))
    return False


def _clean(s: str) -> str:
    return " ".join(html.unescape(_TAGS.sub("", s)).split())


def _real_url(href: str):
    href = html.unescape(href)
    if href.startswith("//"):
        href = "https:" + href
    q = parse_qs(urlparse(href).query)
    if "uddg" in q:  # DuckDuckGo redirect wrapper
        href = unquote(q["uddg"][0])
    u = urlparse(href)
    if u.scheme not in ("http", "https") or u.netloc.endswith("duckduckgo.com"):
        return None  # ads and internal links
    return href


def parse_results(page: str, limit: int = MAX_RESULTS) -> list:
    out, seen = [], set()
    for href, title, rest in _BLOCK.findall(page):
        url = _real_url(href)
        if not url or url in seen:
            continue
        seen.add(url)
        sn = _SNIPPET.search(rest)
        out.append({"title": _clean(title)[:150], "url": url, "snippet": _clean(sn.group(1))[:300] if sn else ""})
        if len(out) >= limit:
            break
    return out


async def search(query: str, limit: int = MAX_RESULTS) -> list:
    """Return [{title, url, snippet}]; [] on any failure (the chat then answers without search)."""
    try:
        async with httpx.AsyncClient(timeout=8, headers={"User-Agent": UA}, follow_redirects=True) as c:
            r = await c.post(DDG_URL, data={"q": query[:300]})
        r.raise_for_status()
        return parse_results(r.text, limit)
    except Exception:
        return []


def context_message(results: list) -> dict:
    lines = [f"Web search results (today is {time.strftime('%Y-%m-%d', time.gmtime())}). "
             "Use them when relevant and cite them as [1], [2]. Do not invent sources."]
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']}\n{r['url']}\n{r['snippet']}")
    return {"role": "system", "content": "\n\n".join(lines)}


def sources_text(results: list) -> str:
    return "\n\n출처\n" + "\n".join(f"[{i}] [{r['title']}]({r['url']})" for i, r in enumerate(results, 1))
