"""Lädt und validiert Skills aus `skills/<name>/`.

Ein Skill besteht aus:
- SKILL.md      Frontmatter (name, description, version, ...) + Anleitung in Prosa
- rules.yaml    maschinenlesbare Regeln, validiert gegen models.RULE_MODELS[name]
- CHANGELOG.md  muss einen Abschnitt `## <version>` für die aktuelle Version enthalten
"""

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ValidationError

from .models import RULE_MODELS, Sourced, Strict

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
MAX_SOURCE_AGE_DAYS = 90


class SkillError(ValueError):
    """Skill ist ungültig. Die Meldung ist für Nicht-Entwickler formuliert."""


@dataclass(frozen=True)
class Skill:
    name: str
    version: str
    description: str
    instructions: str
    rules: Strict
    path: Path
    content_hash: str = field(repr=False)
    meta: dict[str, Any] = field(default_factory=dict, repr=False)


def _read(path: Path) -> str:
    if not path.exists():
        raise SkillError(f"Datei fehlt: {path}")
    return path.read_text(encoding="utf-8")


def _format_validation_error(skill: str, exc: ValidationError) -> str:
    lines = [f"Skill '{skill}': rules.yaml ist ungültig ({exc.error_count()} Fehler)"]
    for err in exc.errors():
        where = " → ".join(str(p) for p in err["loc"])
        lines.append(f"  - {where}: {err['msg']}")
    return "\n".join(lines)


def load_skill(directory: Path) -> Skill:
    name = directory.name
    if name not in RULE_MODELS:
        raise SkillError(f"Unbekannter Skill '{name}'. Bekannt: {sorted(RULE_MODELS)}")

    skill_md = _read(directory / "SKILL.md")
    match = FRONTMATTER.match(skill_md)
    if not match:
        raise SkillError(f"Skill '{name}': SKILL.md braucht einen Kopf zwischen '---'-Zeilen")
    meta = yaml.safe_load(match.group(1)) or {}
    instructions = match.group(2).strip()

    if meta.get("name") != name:
        raise SkillError(f"Skill '{name}': 'name' im Kopf muss '{name}' sein")
    version = str(meta.get("version", ""))
    if not SEMVER.match(version):
        raise SkillError(f"Skill '{name}': Version '{version}' muss die Form 1.2.3 haben")
    if not meta.get("description"):
        raise SkillError(f"Skill '{name}': 'description' fehlt im Kopf")

    changelog = _read(directory / "CHANGELOG.md")
    if not re.search(rf"^## {re.escape(version)}\b", changelog, re.MULTILINE):
        raise SkillError(f"Skill '{name}': CHANGELOG.md hat keinen Abschnitt '## {version}'")

    rules_text = _read(directory / "rules.yaml")
    try:
        raw_rules = yaml.safe_load(rules_text) or {}
    except yaml.YAMLError as exc:
        raise SkillError(f"Skill '{name}': rules.yaml ist kein gültiges YAML: {exc}") from exc
    try:
        rules = RULE_MODELS[name].model_validate(raw_rules)
    except ValidationError as exc:
        raise SkillError(_format_validation_error(name, exc)) from exc

    digest = hashlib.sha256((skill_md + "\n" + rules_text).encode("utf-8")).hexdigest()[:12]
    return Skill(
        name=name,
        version=version,
        description=str(meta["description"]),
        instructions=instructions,
        rules=rules,
        path=directory,
        content_hash=digest,
        meta=meta,
    )


def load_skills(root: Path) -> dict[str, Skill]:
    skills = {d.name: load_skill(d) for d in sorted(root.iterdir()) if (d / "SKILL.md").exists()}
    missing = set(RULE_MODELS) - set(skills)
    if missing:
        raise SkillError(f"Skills fehlen: {sorted(missing)}")
    return skills


def iter_sourced(obj: Any, path: str = "") -> list[tuple[str, Sourced]]:
    """Alle belegten Werte eines Regelobjekts mit ihrem Pfad (für Prüfdatum-Hinweise)."""
    found: list[tuple[str, Sourced]] = []
    if isinstance(obj, Sourced):
        found.append((path, obj))
    elif isinstance(obj, BaseModel):
        for name in type(obj).model_fields:
            found += iter_sourced(getattr(obj, name), f"{path}.{name}" if path else name)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            found += iter_sourced(value, f"{path}.{key}" if path else str(key))
    elif isinstance(obj, list | tuple):
        for i, value in enumerate(obj):
            found += iter_sourced(value, f"{path}[{i}]")
    return found


def stale_sources(skill: Skill, today: date, max_age_days: int = MAX_SOURCE_AGE_DAYS) -> list[str]:
    """Hinweise für Werte, deren Prüfdatum älter als max_age_days ist (kein Fehler)."""
    hints = []
    for path, sourced in iter_sourced(skill.rules):
        age = (today - sourced.checked).days
        if age > max_age_days:
            hints.append(
                f"{skill.name}: {path} zuletzt geprüft am {sourced.checked} "
                f"({age} Tage) – bitte gegen {sourced.source} prüfen"
            )
    return hints
