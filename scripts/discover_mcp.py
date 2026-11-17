"""Erkundet die Galaxus-MCP-Schnittstelle und zeichnet die Antworten als Fixtures auf.

Bewusst sparsam: eine rohe Initialisierungsanfrage (Diagnose), dann Tool-Liste + eine Suche.
Protokoll in output/discover.log (nicht im Repository).
Aufruf:  uv run python scripts/discover_mcp.py
"""

import asyncio
import json
import traceback
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import httpx2
from mcp import Client

SERVER_URL = "https://mcp.galaxus.ch"
ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "mcp"
LOG_FILE = ROOT / "output" / "discover.log"

# Pflichtfeld laut Doku: identifiziert den aufrufenden Agenten (Traffic-Monitoring).
AGENT_INFO = "creative-automation-agent/0.1 (private portfolio project); model: none (discovery)"

SEARCH_ARGS = {
    "query": "Kopfhörer Noise Cancelling",
    "agentInfo": AGENT_INFO,
    "first": 5,
    "maxPrice": 200,
    "language": "de",  # Pflichtfeld laut tools/list (fehlt in der README)
    "userIntent": "Kopfhörer für Pendler bis CHF 200",  # keine Personendaten
}


def log(msg: str) -> None:
    print(msg)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")


def describe_error(exc: BaseException, indent: str = "  ") -> None:
    """Ausnahmegruppen auspacken und Code/Meldung/Daten von MCP-Fehlern zeigen."""
    if isinstance(exc, BaseExceptionGroup):
        for sub in exc.exceptions:
            describe_error(sub, indent)
        return
    log(f"{indent}{type(exc).__name__}: {exc}")
    for attr in ("code", "message", "data", "error"):
        if hasattr(exc, attr):
            log(f"{indent}  {attr} = {getattr(exc, attr)!r}")
    log("".join(traceback.format_exception(exc))[-1500:])


def raw_probe() -> None:
    """Eine rohe initialize-Anfrage, um die wörtliche Serverantwort zu sehen."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "creative-automation-agent-discovery", "version": "0.1"},
        },
    }
    headers = {"Accept": "application/json, text/event-stream"}
    resp = httpx2.post(SERVER_URL, json=payload, headers=headers, timeout=20)
    log(f"[raw] HTTP {resp.status_code}, content-type={resp.headers.get('content-type')}")
    log(f"[raw] mcp-session-id gesetzt: {'mcp-session-id' in resp.headers}")
    log(f"[raw] Antwort (Anfang): {resp.text[:1500]}")


def _dump(model) -> object:
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


def _write(name: str, payload: dict) -> Path:
    path = FIXTURE_DIR / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


async def record() -> None:
    meta = {
        "server_url": SERVER_URL,
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "mcp_sdk_version": version("mcp"),
    }
    # mode="legacy": klassischer initialize-Handshake statt server/discover (Protokoll 2026-07-28).
    async with Client(SERVER_URL, mode="legacy") as client:
        log(f"[sdk] verbunden, Protokoll {client.protocol_version}")
        server = {
            "server_info": _dump(client.server_info) if client.server_info else None,
            "protocol_version": client.protocol_version,
            "instructions": client.instructions,
        }
        tools = await client.list_tools()
        p1 = _write("tools_list.json", {"_meta": meta, **server, "result": _dump(tools)})
        log(f"[sdk] Tools: {[t.name for t in tools.tools]} -> {p1.name}")

        result = await client.call_tool("search_products", SEARCH_ARGS)
        p2 = _write(
            "search_products_kopfhoerer.json",
            {"_meta": {**meta, "arguments": SEARCH_ARGS}, "result": _dump(result)},
        )
        log(f"[sdk] Suche: isError={result.is_error} -> {p2.name}")


def main() -> None:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC).isoformat(timespec="seconds")
    LOG_FILE.write_text(f"Lauf {started}\n", encoding="utf-8")
    log(f"mcp-SDK {version('mcp')}, httpx2 {version('httpx2')}")
    try:
        raw_probe()
    except Exception as exc:  # Diagnose soll den SDK-Versuch nicht verhindern
        log("[raw] fehlgeschlagen:")
        describe_error(exc)
    try:
        asyncio.run(record())
    except BaseException as exc:
        log("[sdk] fehlgeschlagen:")
        describe_error(exc)
    log(f"Protokoll: {LOG_FILE}")


if __name__ == "__main__":
    main()
