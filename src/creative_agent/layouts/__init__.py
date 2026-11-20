"""Modulare Layouts: HTML/CSS-Bausteine je Format, gerendert mit Playwright."""

from .compose import LayoutSpec, compose_html, format_chf, layout_spec
from .render import LayoutRenderer, LayoutReport, analyse

__all__ = [
    "LayoutRenderer",
    "LayoutReport",
    "LayoutSpec",
    "analyse",
    "compose_html",
    "format_chf",
    "layout_spec",
]
