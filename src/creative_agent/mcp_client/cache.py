"""Datei-Cache für Rohantworten der Schnittstelle (siehe ADR 0002).

Gespeichert wird der Rohtext, nicht das normalisierte Ergebnis: Ändert sich die
Normalisierung, gilt sie sofort auch für gecachte Antworten, ohne neue Anfrage.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Any


def cache_key(server_url: str, tool: str, arguments: dict[str, Any]) -> str:
    """Stabiler Schlüssel, unabhängig von der Reihenfolge der Argumente."""
    canonical = json.dumps(
        {"server": server_url, "tool": tool, "args": arguments},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class FileCache:
    def __init__(self, directory: Path, ttl_seconds: int, clock=time.time) -> None:
        self.directory = directory
        self.ttl_seconds = ttl_seconds
        self._clock = clock

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> str | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None  # defekter Eintrag zählt als Fehltreffer
        if self._clock() - entry.get("stored_at", 0) > self.ttl_seconds:
            return None
        return entry.get("text")

    def set(self, key: str, text: str, arguments: dict[str, Any]) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        entry = {"stored_at": self._clock(), "arguments": arguments, "text": text}
        tmp = self._path(key).with_suffix(".tmp")
        tmp.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self._path(key))  # atomar: kein halb geschriebener Eintrag
