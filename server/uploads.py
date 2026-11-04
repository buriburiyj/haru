"""Image uploads: originals live in jun-files .agent/uploads/, read by the vision model on demand."""
import base64
import os
import re
import secrets
from collections import OrderedDict

import httpx

import storage

MAX_BYTES = int(os.environ.get("UPLOAD_MAX_BYTES", str(3 * 1024 * 1024)))
MAX_IMAGES_PER_REQUEST = 3
UPLOAD_DIR = ".agent/uploads"
ID_RE = re.compile(r"^[0-9a-f]{16}\.(jpg|png|webp|gif)$")
MIME = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif"}
_CACHE: "OrderedDict[str, bytes]" = OrderedDict()  # last few images, so a chat right after upload skips GitHub
_CACHE_MAX_ITEMS = 3


class UploadError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


def sniff(data: bytes):
    """Return the extension if the bytes really are an allowed image, else None."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    return None


def valid_id(upload_id: str) -> bool:
    return bool(ID_RE.fullmatch(upload_id or ""))


def _remember(upload_id: str, data: bytes):
    _CACHE[upload_id] = data
    _CACHE.move_to_end(upload_id)
    while len(_CACHE) > _CACHE_MAX_ITEMS:
        _CACHE.popitem(last=False)


async def save(data: bytes, name: str = "") -> dict:
    if not data:
        raise UploadError(400, "empty body")
    if len(data) > MAX_BYTES:
        raise UploadError(413, f"image too large (max {MAX_BYTES // 1024 // 1024} MB)")
    ext = sniff(data)
    if ext is None:
        raise UploadError(415, "only jpeg, png, webp and gif images are accepted")
    upload_id = f"{secrets.token_hex(8)}.{ext}"
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            await storage.put_bytes(c, f"{UPLOAD_DIR}/{upload_id}", data, f"upload {upload_id}")
    except Exception:
        raise UploadError(502, "storage unavailable")
    _remember(upload_id, data)
    return {"id": upload_id, "name": name[:100], "mime": MIME[ext], "size": len(data)}


async def load(upload_id: str):
    """Return (bytes, mime) or None if unknown."""
    if not valid_id(upload_id):
        return None
    data = _CACHE.get(upload_id)
    if data is None:
        data = await storage.read_bytes(f"{UPLOAD_DIR}/{upload_id}")
        if data is None:
            return None
        _remember(upload_id, data)
    return data, MIME[upload_id.rsplit(".", 1)[1]]


def data_uri(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"
