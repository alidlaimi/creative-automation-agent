"""Demo: Produktsuche über die Galaxus-MCP-Schnittstelle.

uv run python -m creative_agent.mcp_client "Kopfhörer Noise Cancelling" --max-price 200
uv run python -m creative_agent.mcp_client "Kopfhörer" --offline   # aus Fixtures, ohne Netz
"""

import argparse
import asyncio
import os
from pathlib import Path

from . import FileCache, FixtureToolCaller, GalaxusProductSearch, LiveToolCaller

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_URL = "https://mcp.galaxus.ch"
AGENT_INFO = "creative-automation-agent/0.1 (private portfolio project); model: none (cli)"


def main() -> None:
    parser = argparse.ArgumentParser(description="Galaxus-Produktsuche über MCP")
    parser.add_argument("query")
    parser.add_argument("--max-price", type=int)
    parser.add_argument("--min-price", type=int)
    parser.add_argument("--first", type=int, default=5)
    parser.add_argument("--language", default="de")
    parser.add_argument("--offline", action="store_true", help="aufgezeichnete Fixtures nutzen")
    args = parser.parse_args()

    server_url = os.environ.get("GALAXUS_MCP_URL", DEFAULT_URL)
    if args.offline:
        caller = FixtureToolCaller(ROOT / "tests" / "fixtures" / "mcp")
    else:
        caller = LiveToolCaller(server_url)
    cache = FileCache(
        ROOT / "data" / "cache" / "mcp",
        ttl_seconds=int(os.environ.get("MCP_CACHE_TTL_SECONDS", "86400")),
    )
    search = GalaxusProductSearch(
        caller, server_url=server_url, agent_info=AGENT_INFO, cache=None if args.offline else cache
    )
    result = asyncio.run(
        search.search(
            args.query,
            language=args.language,
            first=args.first,
            min_price=args.min_price,
            max_price=args.max_price,
        )
    )

    source = "Fixture" if args.offline else ("Cache" if search.live_calls == 0 else "live")
    print(f"{result.total_count} Treffer für {result.query!r} (Quelle: {source})")
    for p in result.products:
        price = f"{p.price.currency} {p.price.amount}" if p.price else "kein Preis"
        rating = f"{p.rating.average}★ ({p.rating.count})" if p.rating else "-"
        print(
            f"  [{p.id}] {p.brand or ''} {p.name} | {price} | {rating} | {', '.join(p.properties)}"
        )


if __name__ == "__main__":
    main()
