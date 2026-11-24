import shutil
from datetime import date
from pathlib import Path

import pytest

from creative_agent.skills import SkillError, load_skill, load_skills, stale_sources
from creative_agent.skills.loader import iter_sourced
from creative_agent.skills.models import BrandVoiceRules, ChannelFormatsRules, FactCheckRules

SKILLS = Path(__file__).resolve().parents[1] / "skills"
RSA_URL = "https://support.google.com/google-ads/answer/7684791"


@pytest.fixture
def skill_copy(tmp_path):
    """Kopie aller Skills, damit Tests Dateien verändern dürfen."""
    target = tmp_path / "skills"
    shutil.copytree(SKILLS, target)
    return target


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} nicht in {path.name}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# ---------- echte Skills ----------


def test_all_skills_load():
    skills = load_skills(SKILLS)
    assert set(skills) == {"kanalformate", "faktencheck", "markenstimme"}
    assert isinstance(skills["kanalformate"].rules, ChannelFormatsRules)
    assert isinstance(skills["faktencheck"].rules, FactCheckRules)
    assert isinstance(skills["markenstimme"].rules, BrandVoiceRules)


def test_every_channel_value_has_source_and_date():
    rules = load_skill(SKILLS / "kanalformate").rules
    sourced = iter_sourced(rules)
    assert len(sourced) > 30
    for path, value in sourced:
        assert value.source and value.checked, path


def test_official_limits_point_to_platform_pages():
    rules = load_skill(SKILLS / "kanalformate").rules
    for path, value in iter_sourced(rules):
        if value.status == "offizielles Limit":
            assert value.source.startswith(
                "https://support.google.com/"
            ) or value.source.startswith("https://www.facebook.com/"), path


def test_known_values_match_official_sources():
    ch = load_skill(SKILLS / "kanalformate").rules.channels
    rsa = ch["google_ads_rsa"].text_fields
    assert (rsa["titel"].max_chars.value, rsa["beschreibung"].max_chars.value) == (30, 90)
    assert rsa["pfad"].max_chars.value == 15
    story = ch["meta_story"].image.safe_zone
    assert (story.top.value, story.bottom.value, story.left.value) == (14, 35, 6)
    assert ch["google_display_banner"].image.max_text_area_percent.value == 20


def test_every_layout_channel_has_image_size():
    for name, channel in load_skill(SKILLS / "kanalformate").rules.channels.items():
        if channel.layout:
            assert channel.image.width.value > 0 and channel.image.height.value > 0, name


def test_brand_voice_is_marked_as_derivation():
    skill = load_skill(SKILLS / "markenstimme")
    assert skill.meta["herkunft"].startswith("Ableitung")
    assert "Ableitung" in skill.instructions


def test_skill_files_contain_no_eszett():
    for path in SKILLS.rglob("*"):
        if path.is_file():
            # erlaubt sind nur Erwähnungen der Regel selbst: «ß» bzw. "ß"
            text = path.read_text(encoding="utf-8").replace("«ß»", "").replace('"ß"', "")
            assert "ß" not in text, path


# ---------- Quellen- und Datumspflicht ----------


def test_value_without_source_fails(skill_copy):
    _edit(
        skill_copy / "kanalformate" / "rules.yaml",
        f'max_zeichen: {{wert: 30, status: offizielles Limit, quelle: "{RSA_URL}", geprueft:',
        "max_zeichen: {wert: 30, status: offizielles Limit, geprueft:",
    )
    with pytest.raises(SkillError, match="quelle"):
        load_skill(skill_copy / "kanalformate")


def test_value_without_check_date_fails(skill_copy):
    _edit(
        skill_copy / "kanalformate" / "rules.yaml",
        f'{{wert: 15, status: offizielles Limit, quelle: "{RSA_URL}", geprueft: 2026-11-17}}',
        f'{{wert: 15, status: offizielles Limit, quelle: "{RSA_URL}"}}',
    )
    with pytest.raises(SkillError, match="geprueft"):
        load_skill(skill_copy / "kanalformate")


def test_unknown_status_fails(skill_copy):
    _edit(skill_copy / "kanalformate" / "rules.yaml", "status: Empfehlung", "status: Bauchgefühl")
    with pytest.raises(SkillError, match="status"):
        load_skill(skill_copy / "kanalformate")


def test_non_https_source_fails(skill_copy):
    _edit(
        skill_copy / "kanalformate" / "rules.yaml",
        f'"{RSA_URL}"',
        '"http://irgendwo.example"',
    )
    with pytest.raises(SkillError, match="Quelle"):
        load_skill(skill_copy / "kanalformate")


def test_typo_in_key_is_reported(skill_copy):
    _edit(skill_copy / "kanalformate" / "rules.yaml", "max_zeichen:", "max_zeichn:")
    with pytest.raises(SkillError, match="max_zeichn"):
        load_skill(skill_copy / "kanalformate")


def test_old_check_date_gives_hint_not_error():
    skill = load_skill(SKILLS / "kanalformate")
    assert stale_sources(skill, today=date(2026, 12, 1)) == []
    hints = stale_sources(skill, today=date(2027, 3, 1))
    assert hints and all("bitte gegen" in h for h in hints)


# ---------- Versionierung ----------


def test_version_must_be_semver(skill_copy):
    _edit(skill_copy / "kanalformate" / "SKILL.md", "version: 1.0.0", "version: neu")
    with pytest.raises(SkillError, match="Version"):
        load_skill(skill_copy / "kanalformate")


def test_version_needs_changelog_entry(skill_copy):
    _edit(skill_copy / "kanalformate" / "SKILL.md", "version: 1.0.0", "version: 1.1.0")
    with pytest.raises(SkillError, match="CHANGELOG"):
        load_skill(skill_copy / "kanalformate")


def test_content_hash_changes_with_rules(skill_copy):
    before = load_skill(skill_copy / "faktencheck").content_hash
    _edit(skill_copy / "faktencheck" / "rules.yaml", "- Testsieger", "- Testsiegerin")
    assert load_skill(skill_copy / "faktencheck").content_hash != before


def test_name_must_match_folder(skill_copy):
    _edit(skill_copy / "markenstimme" / "SKILL.md", "name: markenstimme", "name: tonalitaet")
    with pytest.raises(SkillError, match="name"):
        load_skill(skill_copy / "markenstimme")


def test_missing_skill_is_reported(skill_copy):
    shutil.rmtree(skill_copy / "faktencheck")
    with pytest.raises(SkillError, match="faktencheck"):
        load_skills(skill_copy)


def test_invalid_yaml_is_reported(skill_copy):
    (skill_copy / "markenstimme" / "rules.yaml").write_text("anrede: [du", encoding="utf-8")
    with pytest.raises(SkillError, match="YAML"):
        load_skill(skill_copy / "markenstimme")


def test_brand_voice_examples_are_in_skill_text():
    """Die maschinenlesbaren Beispiele müssen dieselben sein wie in SKILL.md."""
    skill = load_skill(SKILLS / "markenstimme")
    assert skill.rules.examples_not_to_copy
    for example in skill.rules.examples_not_to_copy:
        assert f"«{example}»" in skill.instructions, example
