"""Skills: versionierte, ohne Code änderbare Regeln (Markenstimme, Kanalformate, Faktencheck)."""

from .loader import Skill, SkillError, load_skill, load_skills, stale_sources

__all__ = ["Skill", "SkillError", "load_skill", "load_skills", "stale_sources"]
