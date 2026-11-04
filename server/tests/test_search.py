import asyncio
import sys
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import search  # noqa: E402

REAL = httpx.AsyncClient

PAGE = """
<div class="result__body"><h2><a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa%3Fx%3D1&amp;rut=zz">Example &amp; <b>Title</b></a></h2>
<a class="result__snippet" href="x">A <b>short</b> snippet &quot;here&quot;</a></div>
<div class="result__body"><h2><a rel="nofollow" class="result__a" href="https://duckduckgo.com/y.js?ad=1">Ad</a></h2></div>
<div class="result__body"><h2><a rel="nofollow" class="result__a" href="https://example.org/b">Second</a></h2></div>
<div class="result__body"><h2><a rel="nofollow" class="result__a" href="https://example.org/b">Dup</a></h2></div>
"""


class SearchTest(unittest.TestCase):
    def tearDown(self):
        httpx.AsyncClient = REAL

    def test_parse_unwraps_redirect_skips_ads_and_dups(self):
        r = search.parse_results(PAGE)
        self.assertEqual([x["url"] for x in r], ["https://example.com/a?x=1", "https://example.org/b"])
        self.assertEqual(r[0]["title"], "Example & Title")
        self.assertEqual(r[0]["snippet"], 'A short snippet "here"')

    def test_needs_search(self):
        u = lambda t: [{"role": "user", "content": t}]  # noqa: E731
        self.assertTrue(search.needs_search(u("오늘 환율 알려줘")))
        self.assertTrue(search.needs_search(u("What is the latest iPhone?")))
        self.assertFalse(search.needs_search(u("I know quicksort")))  # 'know' must not match 'now'
        self.assertFalse(search.needs_search(u("안녕하세요")))
        self.assertTrue(search.needs_search(u("hello"), "on"))
        self.assertFalse(search.needs_search(u("오늘 뉴스"), "off"))

    def test_search_returns_results_and_never_raises(self):
        class Mocked(REAL):
            def __init__(self, *a, **kw):
                kw["transport"] = httpx.MockTransport(lambda req: httpx.Response(200, text=PAGE))
                super().__init__(*a, **kw)

        httpx.AsyncClient = Mocked
        self.assertEqual(len(asyncio.run(search.search("q"))), 2)

        class Broken(REAL):
            def __init__(self, *a, **kw):
                kw["transport"] = httpx.MockTransport(lambda req: httpx.Response(503))
                super().__init__(*a, **kw)

        httpx.AsyncClient = Broken
        self.assertEqual(asyncio.run(search.search("q")), [])

    def test_sources_text_uses_markdown_links(self):
        t = search.sources_text([{"title": "T", "url": "https://u"}])
        self.assertIn("[1] [T](https://u)", t)


if __name__ == "__main__":
    unittest.main()
