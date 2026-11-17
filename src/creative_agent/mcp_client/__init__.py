"""MCP-Client für die öffentliche Galaxus-Produktsuche."""

from .cache import FileCache
from .callers import FixtureToolCaller, LiveToolCaller, MCPToolError
from .client import GalaxusProductSearch, SearchArgumentError
from .normalize import MCPDataError
from .schema import Image, Price, Product, Rating, ReviewSummary, SearchResult

__all__ = [
    "FileCache",
    "FixtureToolCaller",
    "GalaxusProductSearch",
    "Image",
    "LiveToolCaller",
    "MCPDataError",
    "MCPToolError",
    "Price",
    "Product",
    "Rating",
    "ReviewSummary",
    "SearchArgumentError",
    "SearchResult",
]
