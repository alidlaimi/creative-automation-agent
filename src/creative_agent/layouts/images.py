"""Lädt Produktbilder mit einem ehrlichen HTTP-Client und speichert sie lokal zwischen.

Warum nicht direkt im Browser? Das CDN beantwortet Bildanfragen des automatisierten (headless)
Browsers nicht. Wir tarnen den Browser nicht, sondern laden das Bild – wie die MCP-Abfragen –
mit einem Client, der sich als dieses Projekt ausweist, und betten es ein.
Bilder liegen nur lokal (data/cache/images, nicht im Repository).
"""

import base64
import hashlib
import json
from pathlib import Path

import httpx2

USER_AGENT = "creative-automation-agent/0.1 (private portfolio project)"
MAX_BYTES = 8_000_000


class ImageFetcher:
    def __init__(self, cache_dir: Path, timeout_seconds: float = 15) -> None:
        self.cache_dir = cache_dir
        self.timeout_seconds = timeout_seconds
        self.errors: dict[str, str] = {}

    def _paths(self, url: str) -> tuple[Path, Path]:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{key}.bin", self.cache_dir / f"{key}.json"

    def data_uri(self, url: str) -> str | None:
        """Bild als data-URI oder None (Grund in self.errors[url])."""
        blob, meta = self._paths(url)
        if blob.exists() and meta.exists():
            content_type = json.loads(meta.read_text("utf-8"))["content_type"]
            return self._encode(blob.read_bytes(), content_type)
        try:
            resp = httpx2.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=self.timeout_seconds,
                follow_redirects=True,
            )
        except Exception as exc:  # Netzwerkfehler: Gate meldet «Bild nicht geladen»
            self.errors[url] = f"{type(exc).__name__}: {exc}"
            return None
        content_type = resp.headers.get("content-type", "").split(";")[0].strip()
        if resp.status_code != 200 or not content_type.startswith("image/"):
            self.errors[url] = f"HTTP {resp.status_code}, {content_type or 'ohne Typ'}"
            return None
        if len(resp.content) > MAX_BYTES:
            self.errors[url] = f"Bild zu gross ({len(resp.content)} Bytes)"
            return None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        blob.write_bytes(resp.content)
        meta.write_text(json.dumps({"url": url, "content_type": content_type}), "utf-8")
        return self._encode(resp.content, content_type)

    @staticmethod
    def _encode(data: bytes, content_type: str) -> str:
        return f"data:{content_type};base64,{base64.b64encode(data).decode('ascii')}"
