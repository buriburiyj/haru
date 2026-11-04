"""Run in a fresh process by test_memory_budget.py: exercise the server with large inputs, print peak RSS in MB."""
import os
import resource
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.update(SESSION_SECRET="probe", GITHUB_TOKEN="x", GROQ_API_KEY="x", NVIDIA_API_KEY="x",
                  CRED_FILE=str(Path(tempfile.mkdtemp()) / "c.json"), QUEUE_DIR=tempfile.mkdtemp(),
                  USAGE_FILE=str(Path(tempfile.mkdtemp()) / "u.json"))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
import search  # noqa: E402
import uploads  # noqa: E402

big_png = b"\x89PNG\r\n\x1a\n" + os.urandom(uploads.MAX_BYTES - 100)
answer = "word " * 40000  # ~200 KB answer from a model


async def fake_route(messages, mode):
    yield "model", "m"
    for i in range(0, len(answer), 400):
        yield "delta", answer[i:i + 400]


async def fake_save(cid, data):
    return True, {"id": cid, "title": "t"}


async def fake_put(client, path, data, msg):
    return None


main.router.route, main.storage.save_chat, main.storage.put_bytes = fake_route, fake_save, fake_put
main.memory._mem = {}
c = TestClient(main.app)
c.headers["Authorization"] = "Bearer " + main._sign(int(time.time()) + 600)

history = [{"role": "user" if i % 2 == 0 else "assistant", "content": "x" * 2000} for i in range(100)]  # ~200 KB
for i in range(30):
    r = c.post("/chat", json={"chat_id": f"c{i}", "messages": history})
    assert r.status_code == 200 and "event: done" in r.text, r.text[:200]
for i in range(4):
    assert c.post("/uploads", content=big_png).status_code == 200
page = '<a class="result__a" href="https://e.com/1">T</a>' * 50
for i in range(200):
    search.parse_results(page)

rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
print(round(rss / (1024 * 1024) if sys.platform == "darwin" else rss / 1024, 1))
