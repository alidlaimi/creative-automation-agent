import asyncio
from pathlib import Path

import pytest

from creative_agent.mcp_client import (
    FileCache,
    FixtureToolCaller,
    GalaxusProductSearch,
    SearchArgumentError,
)
from creative_agent.mcp_client.cache import cache_key

FIXTURES = Path(__file__).parent / "fixtures" / "mcp"
URL = "https://mcp.galaxus.ch"


def make_search(tmp_path, ttl=3600):
    caller = FixtureToolCaller(FIXTURES)
    cache = FileCache(tmp_path / "cache", ttl_seconds=ttl)
    search = GalaxusProductSearch(
        caller, server_url=URL, agent_info="test-agent", cache=cache, min_interval_seconds=0
    )
    return search, caller


def test_search_sends_required_fields(tmp_path):
    search, caller = make_search(tmp_path)
    asyncio.run(search.search("Kopfhörer", max_price=200, user_intent="Pendeln"))
    sent = caller.calls[0]["arguments"]
    assert sent["agentInfo"] == "test-agent"
    assert sent["language"] == "de"
    assert sent["maxPrice"] == 200 and "minPrice" not in sent


def test_second_identical_search_uses_cache(tmp_path):
    search, caller = make_search(tmp_path)
    asyncio.run(search.search("Kopfhörer", max_price=200))
    asyncio.run(search.search(" Kopfhörer ", max_price=200, user_intent="anders"))
    assert len(caller.calls) == 1  # userIntent ändert das Ergebnis nicht -> kein neuer Aufruf


def test_different_filter_is_a_new_request(tmp_path):
    search, caller = make_search(tmp_path)
    asyncio.run(search.search("Kopfhörer", max_price=200))
    asyncio.run(search.search("Kopfhörer", max_price=150))
    assert len(caller.calls) == 2


def test_expired_cache_entry_triggers_new_request(tmp_path):
    now = [1000.0]
    caller = FixtureToolCaller(FIXTURES)
    cache = FileCache(tmp_path, ttl_seconds=60, clock=lambda: now[0])
    search = GalaxusProductSearch(
        caller, server_url=URL, agent_info="t", cache=cache, min_interval_seconds=0
    )
    asyncio.run(search.search("Kopfhörer"))
    now[0] += 61
    asyncio.run(search.search("Kopfhörer"))
    assert len(caller.calls) == 2


def test_corrupt_cache_entry_is_ignored(tmp_path):
    cache = FileCache(tmp_path, ttl_seconds=60)
    (tmp_path / "abc.json").write_text("{kaputt", encoding="utf-8")
    assert cache.get("abc") is None


def test_cache_key_ignores_argument_order():
    assert cache_key(URL, "t", {"a": 1, "b": 2}) == cache_key(URL, "t", {"b": 2, "a": 1})


@pytest.mark.parametrize(
    "kwargs",
    [
        {"query": "  "},
        {"query": "x", "language": "es"},
        {"query": "x", "first": 51},
        {"query": "x", "first": 0},
        {"query": "x", "max_price": 99.5},
        {"query": "x", "min_price": 300, "max_price": 200},
    ],
)
def test_invalid_arguments_are_rejected_before_any_request(tmp_path, kwargs):
    search, caller = make_search(tmp_path)
    query = kwargs.pop("query")
    with pytest.raises(SearchArgumentError):
        asyncio.run(search.search(query, **kwargs))
    assert caller.calls == []
