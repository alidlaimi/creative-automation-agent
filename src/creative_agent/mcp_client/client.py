"""Galaxus-Produktsuche: Validierung, Cache, Mindestabstand, Normalisierung."""

import asyncio
import time
from typing import Any, Literal

from .cache import FileCache, cache_key
from .callers import ToolCaller
from .normalize import parse_search_payload
from .schema import SearchResult

Language = Literal["en", "de", "fr", "it", "nl"]
LANGUAGES: tuple[str, ...] = ("en", "de", "fr", "it", "nl")
TOOL = "search_products"


class SearchArgumentError(ValueError):
    """Ungültige Suchparameter, abgefangen vor der Anfrage."""


class GalaxusProductSearch:
    def __init__(
        self,
        caller: ToolCaller,
        *,
        server_url: str,
        agent_info: str,
        cache: FileCache | None = None,
        min_interval_seconds: float = 1.0,
    ) -> None:
        self.caller = caller
        self.server_url = server_url
        self.agent_info = agent_info
        self.cache = cache
        self.min_interval_seconds = min_interval_seconds
        self._last_live_call = 0.0
        self.live_calls = 0

    @staticmethod
    def _validate(query: str, language: str, first: int, min_price, max_price) -> None:
        # Grenzen aus dem inputSchema von tools/list (docs/quellen/galaxus-mcp.md)
        if not query.strip():
            raise SearchArgumentError("Suchbegriff ist leer")
        if language not in LANGUAGES:
            raise SearchArgumentError(f"Sprache {language!r} nicht unterstützt: {LANGUAGES}")
        if not 1 <= first <= 50:
            raise SearchArgumentError("first muss zwischen 1 und 50 liegen")
        for name, value in (("min_price", min_price), ("max_price", max_price)):
            if value is not None and (not isinstance(value, int) or not 1 <= value <= 1_000_000):
                raise SearchArgumentError(f"{name} muss eine ganze Zahl von 1 bis 1000000 sein")
        if min_price is not None and max_price is not None and min_price > max_price:
            raise SearchArgumentError("min_price ist grösser als max_price")

    async def search(
        self,
        query: str,
        *,
        language: Language = "de",
        first: int = 10,
        min_price: int | None = None,
        max_price: int | None = None,
        user_intent: str | None = None,
    ) -> SearchResult:
        self._validate(query, language, first, min_price, max_price)

        # Ergebnisrelevante Argumente bilden den Cache-Schlüssel. agentInfo und userIntent
        # beeinflussen laut Tool-Beschreibung die Ergebnisse nicht ("analytics only").
        result_args: dict[str, Any] = {"query": query.strip(), "language": language, "first": first}
        if min_price is not None:
            result_args["minPrice"] = min_price
        if max_price is not None:
            result_args["maxPrice"] = max_price
        key = cache_key(self.server_url, TOOL, result_args)

        text = self.cache.get(key) if self.cache else None
        if text is None:
            call_args = {**result_args, "agentInfo": self.agent_info}
            if user_intent:
                call_args["userIntent"] = user_intent
            await self._respect_interval()
            text = await self.caller(TOOL, call_args)
            self.live_calls += 1
            if self.cache:
                self.cache.set(key, text, result_args)
        return parse_search_payload(text, query=query.strip())

    async def _respect_interval(self) -> None:
        """Rücksicht auf den Anbieter: mindestens min_interval_seconds zwischen Anfragen."""
        wait = self._last_live_call + self.min_interval_seconds - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_live_call = time.monotonic()
