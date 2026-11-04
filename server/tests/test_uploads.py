import asyncio
import base64
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["SESSION_SECRET"] = "test-secret"
os.environ.setdefault("CRED_FILE", str(Path(tempfile.mkdtemp()) / "creds.json"))
os.environ["GITHUB_TOKEN"] = "x"

REAL = httpx.AsyncClient

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

main.memory._mem = {}  # no network: memory index is treated as loaded and empty
import uploads  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
JPG = b"\xff\xd8\xff\xe0" + b"0" * 64


def client():
    c = TestClient(main.app)
    c.headers["Authorization"] = f"Bearer {main._sign(int(time.time()) + 60)}"
    return c


class FakeStore:
    def __init__(self):
        self.files, self.down = {}, False

    def __call__(self, req):
        if self.down:
            return httpx.Response(500)
        path = req.url.path.split("/contents/", 1)[1]
        if req.method == "PUT":
            self.files[path] = base64.b64decode(json.loads(req.content)["content"])
            return httpx.Response(201, json={})
        if path in self.files:
            return httpx.Response(200, content=self.files[path])
        return httpx.Response(404)


class UploadTest(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()

        class Mocked(REAL):
            def __init__(s, *a, **kw):
                kw["transport"] = httpx.MockTransport(self.store)
                super().__init__(*a, **kw)

        httpx.AsyncClient = Mocked
        uploads._CACHE.clear()

    def tearDown(self):
        httpx.AsyncClient = REAL

    def test_sniff_checks_real_bytes_not_headers(self):
        self.assertEqual(uploads.sniff(PNG), "png")
        self.assertEqual(uploads.sniff(JPG), "jpg")
        self.assertIsNone(uploads.sniff(b"<html>not an image</html>"))
        self.assertIsNone(uploads.sniff(b"MZ\x90\x00"))

    def test_upload_stores_original_and_serves_it(self):
        r = client().post("/uploads?name=cat.png", content=PNG, headers={"Content-Type": "image/png"})
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertEqual((d["mime"], d["size"], d["name"]), ("image/png", len(PNG), "cat.png"))
        self.assertIn(f".agent/uploads/{d['id']}", self.store.files)
        uploads._CACHE.clear()  # force a read from the store
        g = client().get(f"/uploads/{d['id']}")
        self.assertEqual((g.status_code, g.content, g.headers["content-type"]), (200, PNG, "image/png"))

    def test_rejects_big_non_image_and_empty(self):
        old = uploads.MAX_BYTES
        uploads.MAX_BYTES = 100
        try:
            self.assertEqual(client().post("/uploads", content=b"\x89PNG\r\n\x1a\n" + b"0" * 200).status_code, 413)
        finally:
            uploads.MAX_BYTES = old
        self.assertEqual(client().post("/uploads", content=b"hello world").status_code, 415)
        self.assertEqual(client().post("/uploads", content=b"").status_code, 400)
        self.assertEqual(self.store.files, {})

    def test_storage_failure_is_502_and_needs_session(self):
        self.store.down = True
        self.assertEqual(client().post("/uploads", content=PNG).status_code, 502)
        self.assertEqual(TestClient(main.app).post("/uploads", content=PNG).status_code, 401)

    def test_bad_ids_are_404(self):
        for bad in ("..%2Fsecret", "abc.png", "0123456789abcdef.exe", "0123456789abcdef.png"):
            self.assertEqual(client().get(f"/uploads/{bad}").status_code, 404, bad)

    def test_chat_with_image_uses_vision_model_and_content_array(self):
        up = client().post("/uploads", content=JPG).json()
        seen = {}

        async def spy(messages, mode):
            seen["m"], seen["mode"] = messages, mode
            yield "model", mode
            yield "delta", "a cat"

        async def fake_save(cid, data):
            seen["saved"] = data
            return True, {"id": cid, "title": "T"}

        orig = (main.router.route, main.storage.save_chat)
        main.router.route, main.storage.save_chat = spy, fake_save
        try:
            r = client().post("/chat", json={"chat_id": "p1", "mode": "hard", "messages": [
                {"role": "user", "content": "what is this?", "images": [up["id"], "../evil.png"]}]})
        finally:
            main.router.route, main.storage.save_chat = orig
        self.assertEqual(seen["mode"], main.router.VISION_MODEL)
        parts = seen["m"][0]["content"]
        self.assertEqual(parts[0], {"type": "text", "text": "what is this?"})
        self.assertTrue(parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))
        self.assertEqual(len(parts), 2)  # the invalid id was dropped
        self.assertEqual(seen["saved"]["messages"][0]["images"], [up["id"]])  # ids saved, never base64
        self.assertNotIn("base64", json.dumps(seen["saved"]))

    def test_missing_image_notice_and_normal_routing(self):
        seen = {}

        async def spy(messages, mode):
            seen["mode"] = mode
            yield "delta", "x"

        async def fake_save(cid, data):
            return True, {"id": cid, "title": "T"}

        orig = (main.router.route, main.storage.save_chat)
        main.router.route, main.storage.save_chat = spy, fake_save
        try:
            r = client().post("/chat", json={"messages": [
                {"role": "user", "content": "hi", "images": ["0123456789abcdef.png"]}]})
        finally:
            main.router.route, main.storage.save_chat = orig
        self.assertIn("찾지 못했어요", r.text)
        self.assertEqual(seen["mode"], "auto")


if __name__ == "__main__":
    unittest.main()
