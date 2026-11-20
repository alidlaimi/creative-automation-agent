"""Agentic Workflow: Briefing → Produkte (MCP) → Textvarianten je Kanal und Zielgruppe."""

from .models import RunRecord
from .run import run_workflow, save_run

__all__ = ["RunRecord", "run_workflow", "save_run"]
