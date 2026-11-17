"""Skills prüfen – für das Kreativ-Team nach jeder Änderung.

uv run python -m creative_agent.skills
"""

import sys
from datetime import date
from pathlib import Path

from .loader import SkillError, load_skills, stale_sources

ROOT = Path(__file__).resolve().parents[3] / "skills"


def main() -> int:
    try:
        skills = load_skills(ROOT)
    except SkillError as exc:
        print(f"FEHLER\n{exc}")
        return 1
    for skill in skills.values():
        print(f"OK  {skill.name} v{skill.version} ({skill.content_hash})")
    hints = [h for s in skills.values() for h in stale_sources(s, date.today())]
    for hint in hints:
        print(f"HINWEIS {hint}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
