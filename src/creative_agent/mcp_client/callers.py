"""Austauschbare Aufrufer: live gegen Galaxus oder offline aus aufgezeichneten Fixtures.

Der Client kennt nur das Protokoll `ToolCaller`. So laufen Tests und CI ohne Netz,
und die Demo hat einen Notfallmodus, falls das WLAN im Gespräch streikt.
"""

import json
from pathlib import Path
from typing import Any, Protocol

from mcp import Client


class MCPToolError(RuntimeError):
    """Die Schnittstelle hat einen Fehler gemeldet."""


class ToolCaller(Protocol):
    async def __call__(self, tool: str, arguments: dict[str, Any]) -> str:
        """Ruft ein Tool auf und gibt den Textinhalt der Antwort zurück."""
        ...


def _first_text(content: list[Any]) -> str:
    for block in content:
        if getattr(block, "type", None) == "text":
            return block.text
    raise MCPToolError("Antwort enthält keinen Textinhalt")


class LiveToolCaller:
    def __init__(self, server_url: str, mode: str = "legacy", timeout_seconds: float = 30) -> None:
        # mode="legacy": klassischer initialize-Handshake. Der Galaxus-Server spricht
        # Protokoll 2025-xx, nicht den 2026er Weg über server/discover.
        self.server_url = server_url
        self.mode = mode
        self.timeout_seconds = timeout_seconds

    async def __call__(self, tool: str, arguments: dict[str, Any]) -> str:
        async with Client(
            self.server_url, mode=self.mode, read_timeout_seconds=self.timeout_seconds
        ) as client:
            result = await client.call_tool(tool, arguments)
        if result.is_error:
            raise MCPToolError(_first_text(result.content))
        return _first_text(result.content)


class FixtureToolCaller:
    """Spielt aufgezeichnete Antworten ab. Wählt die Fixture mit passenden Argumenten,
    sonst die erste vorhandene (für Tests und Offline-Demo)."""

    def __init__(self, fixture_dir: Path) -> None:
        self.fixtures = [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(fixture_dir.glob("search_products_*.json"))
        ]
        if not self.fixtures:
            raise FileNotFoundError(f"Keine Fixtures in {fixture_dir}")
        self.calls: list[dict[str, Any]] = []

    async def __call__(self, tool: str, arguments: dict[str, Any]) -> str:
        self.calls.append({"tool": tool, "arguments": arguments})
        query = arguments.get("query")
        match = next(
            (f for f in self.fixtures if f["_meta"]["arguments"].get("query") == query),
            self.fixtures[0],
        )
        return match["result"]["content"][0]["text"]
