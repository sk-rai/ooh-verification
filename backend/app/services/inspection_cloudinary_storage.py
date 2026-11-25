"""Private Cloudinary raw originals. Provider identifiers stay in this adapter."""
import asyncio
from hashlib import sha1, sha256
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from fastapi import HTTPException


class CloudinaryOriginalStore:

    def __init__(self, *, cloud: str, folder: str, key: str, secret: str,
                 cleanup_key: str | None = None, cleanup_secret: str | None = None):
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", cloud) or not re.fullmatch(r"[a-zA-Z0-9_/-]+", folder):
            raise ValueError("Invalid Cloudinary storage location")
        if not key or not secret or bool(cleanup_key) != bool(cleanup_secret) or cleanup_key == key:
            raise ValueError("Invalid Cloudinary credential configuration")
        self.base = f"https://api.cloudinary.com/v1_1/{cloud}"
        self.folder = folder.strip("/")
        if not self.folder or any(not part for part in self.folder.split("/")):
            raise ValueError("Invalid Cloudinary folder")
        self.backend_id = sha256(f"cloudinary:v1:{cloud}:{self.folder}".encode()).hexdigest()
        self.credentials = key, secret
        self.cleanup_credentials = (cleanup_key, cleanup_secret) if cleanup_key else None

    def _id(self, reservation_id: UUID) -> str:
        return f"{self.folder}/{UUID(str(reservation_id))}.original"

    def _signed(self, fields: dict, credentials) -> dict:
        key, secret = credentials
        params = fields | {"timestamp": int(time.time())}
        source = "&".join(f"{name}={value}" for name, value in sorted(params.items()))
        return params | {"api_key": key, "signature": sha1((source + secret).encode()).hexdigest()}

    def _call(self, path: str, *, data=None, content_type=None, limit: int = 65536) -> tuple[int, bytes]:
        headers = {"Content-Type": content_type} if content_type else {}
        try:
            with urlopen(Request(self.base + path, data=data, headers=headers), timeout=15) as response:
                content = response.read(limit + 1)
                if len(content) > limit:
                    raise HTTPException(409, "INSPECTION_ORIGINAL_CONFLICT")
                return response.status, content
        except HTTPError as error:
            code = error.code
            error.close()
            return code, b""
        except (URLError, TimeoutError, OSError):
            raise HTTPException(503, "INSPECTION_STORAGE_UNAVAILABLE") from None

    def _create(self, reservation_id: UUID, content: bytes) -> None:
        params = self._signed({
            "public_id": self._id(reservation_id), "asset_folder": self.folder,
            "type": "authenticated", "overwrite": "false",
        }, self.credentials)
        boundary = uuid4().hex
        parts = [
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
            for name, value in params.items()
        ]
        parts.extend((
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="original"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n".encode(),
            content, f"\r\n--{boundary}--\r\n".encode(),
        ))
        status, _ = self._call("/raw/upload", data=b"".join(parts),
                               content_type=f"multipart/form-data; boundary={boundary}")
        if status not in (200, 201, 409, 412):
            raise HTTPException(503, "INSPECTION_STORAGE_UNAVAILABLE")

    async def create_if_absent(self, reservation_id: UUID, content: bytes) -> None:
        await asyncio.to_thread(self._create, reservation_id, content)

    async def retrieve(self, reservation_id: UUID, *, limit: int) -> bytes:
        params = self._signed({"public_id": self._id(reservation_id), "type": "authenticated"}, self.credentials)
        status, content = await asyncio.to_thread(self._call, "/raw/download?" + urlencode(params), limit=limit)
        if status == 404:
            raise HTTPException(409, "CAPTURE_ORIGINAL_NOT_STORED")
        if status != 200:
            raise HTTPException(503, "INSPECTION_STORAGE_UNAVAILABLE")
        return content

    async def delete_abandoned(self, reservation_id: UUID) -> None:
        if self.cleanup_credentials is None:
            raise HTTPException(503, "INSPECTION_STORAGE_CLEANUP_UNAVAILABLE")
        params = self._signed({"public_id": self._id(reservation_id), "type": "authenticated"},
                              self.cleanup_credentials)
        status, payload = await asyncio.to_thread(
            self._call, "/raw/destroy", data=urlencode(params).encode(),
            content_type="application/x-www-form-urlencoded",
        )
        if status != 200 or json.loads(payload).get("result") not in ("ok", "not found"):
            raise HTTPException(503, "INSPECTION_STORAGE_CLEANUP_UNAVAILABLE")
