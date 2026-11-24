"""Deterministische Gate-Regeln. Jede Funktion liefert Meldungen, keine Ausnahmen."""

import re
from difflib import SequenceMatcher

from ..layouts import LayoutReport
from ..mcp_client import Product
from ..skills import Skill
from ..skills.models import BrandVoiceRules, Channel, FactCheckRules
from ..workflow.models import Variant
from .findings import Finding, severity_for, source_of
from .text import (
    find_prices,
    find_unit_values,
    normalize,
    numbers,
    term_pattern,
    to_decimal,
    unit_pattern,
    word_numbers,
    words,
)

INJECTION_HINTS = [
    "ignoriere",
    "ignore previous",
    "ignore all",
    "system prompt",
    "neue anweisung",
    "du bist jetzt",
    "you are now",
]


def texts_of(variant: Variant) -> list[tuple[str, str]]:
    """(Feldname, Text) für alle veröffentlichten Textfelder; Listen werden aufgefächert."""
    out = []
    for key, value in variant.fields.items():
        if isinstance(value, list):
            out += [(f"{key}[{i + 1}]", str(v)) for i, v in enumerate(value)]
        else:
            out.append((key, str(value)))
    return out


# ---------- 1. Formate (Skill kanalformate) ----------


def check_format(variant: Variant, channel: Channel, skill: Skill) -> list[Finding]:
    tag = f"kanalformate {skill.version}"
    findings: list[Finding] = []
    for key, spec in channel.text_fields.items():
        value = variant.fields.get(key)
        if value in (None, "", []):
            findings.append(
                Finding(
                    rule="feld_fehlt",
                    severity="rot",
                    field=key,
                    message=f"{spec.label} fehlt",
                    source=tag,
                )
            )
            continue
        items = value if isinstance(value, list) else [value]
        if isinstance(value, list):
            n = len(items)
            if spec.min_count and n < int(spec.min_count.value):
                findings.append(
                    Finding(
                        rule="anzahl",
                        severity=severity_for(spec.min_count),
                        field=key,
                        message=f"{n} {spec.label}, mindestens {spec.min_count.value} nötig",
                        source=source_of(spec.min_count),
                    )
                )
            if spec.max_count and n > int(spec.max_count.value):
                findings.append(
                    Finding(
                        rule="anzahl",
                        severity=severity_for(spec.max_count),
                        field=key,
                        message=f"{n} {spec.label}, höchstens {spec.max_count.value} erlaubt",
                        source=source_of(spec.max_count),
                    )
                )
        for i, item in enumerate(items, 1):
            name = f"{key}[{i}]" if isinstance(value, list) else key
            text = str(item).strip()
            if not text:
                findings.append(
                    Finding(
                        rule="feld_leer",
                        severity="rot",
                        field=name,
                        message="Leerer Eintrag",
                        source=tag,
                    )
                )
                continue
            length = len(text)
            if spec.max_chars and length > int(spec.max_chars.value):
                findings.append(
                    Finding(
                        rule="zeichenlimit",
                        severity=severity_for(spec.max_chars),
                        field=name,
                        message=f"{length} Zeichen, max. {spec.max_chars.value} "
                        f"({spec.max_chars.status}): «{text}»",
                        source=source_of(spec.max_chars),
                    )
                )
            if spec.min_chars and length < int(spec.min_chars.value):
                findings.append(
                    Finding(
                        rule="zeichenlimit",
                        severity=severity_for(spec.min_chars),
                        field=name,
                        message=f"{length} Zeichen, empfohlen mind. {spec.min_chars.value}",
                        source=source_of(spec.min_chars),
                    )
                )
    required = channel.required_elements.value if channel.required_elements else []
    if "cta" in required and not str(variant.fields.get("cta", "")).strip():
        findings.append(
            Finding(
                rule="pflichtangabe",
                severity="rot",
                field="cta",
                message="Call-to-Action fehlt",
                source=source_of(channel.required_elements),
            )
        )
    return findings


# ---------- 2. Bildregeln (Messbericht aus dem Rendering) ----------


def check_layout(report: LayoutReport | None, channel: Channel) -> list[Finding]:
    if channel.layout is None:
        return []
    if report is None:
        return [
            Finding(
                rule="layout_fehlt",
                severity="gelb",
                message="Kein Messbericht – Layout nicht gerendert oder nicht geprüft",
            )
        ]
    img = channel.image
    zone = img.safe_zone if img else None
    zone_value = None
    if zone:
        zone_value = next((z for z in (zone.top, zone.bottom, zone.left, zone.right) if z), None)
    findings = [
        Finding(
            rule="sichere_zone",
            severity=severity_for(zone_value),
            field=v.split()[0],
            message=v,
            source=source_of(zone_value),
        )
        for v in report.safe_zone_violations
    ]
    findings += [
        Finding(
            rule="text_ueberlauf",
            severity="rot",
            field=b,
            message=f"Text im Baustein «{b}» ist abgeschnitten",
        )
        for b in report.overflowing
    ]
    if img and img.max_text_area_percent and report.max_text_area_percent is not None:
        limit = float(img.max_text_area_percent.value)
        if report.text_area_percent > limit:
            findings.append(
                Finding(
                    rule="textanteil",
                    severity=severity_for(img.max_text_area_percent),
                    message=f"Text bedeckt {report.text_area_percent} % des Bildes, "
                    f"max. {limit:g} %",
                    source=source_of(img.max_text_area_percent),
                )
            )
    if not report.image_loaded:
        findings.append(
            Finding(
                rule="bild",
                severity="rot",
                field="produktbild",
                message="Produktbild wurde nicht geladen",
            )
        )
    findings += [
        Finding(
            rule="pflichtangabe",
            severity="rot",
            field=m,
            message=f"Pflichtelement «{m}» fehlt im Layout",
            source=source_of(channel.required_elements),
        )
        for m in report.missing_elements
    ]
    return findings


# ---------- 3. Faktencheck (Skill faktencheck, gegen genau dieses Produkt) ----------


def _evidence(product: Product, fields: list[str]) -> str:
    parts = {
        "name": " ".join(x for x in (product.brand, product.name) if x),
        "brand": product.brand or "",
        "product_type": product.product_type or "",
        "properties": ", ".join(product.properties),
        "description": product.description or "",
    }
    return normalize(" | ".join(parts[f] for f in fields if parts.get(f)))


def _without_name(text: str, product: Product) -> str:
    """Produktname und Marke ausblenden: «Barista Express» ist kein Lieferversprechen."""
    for part in sorted(filter(None, [product.name, product.brand]), key=len, reverse=True):
        text = re.sub(re.escape(normalize(part)), " ", text, flags=re.IGNORECASE)
    return text


def check_facts(variant: Variant, product: Product, skill: Skill) -> list[Finding]:
    rules: FactCheckRules = skill.rules
    tag = f"faktencheck {skill.version}"
    fields = list(rules.evidence_fields)
    if _injection_hits(product):
        # Ein Text, der Anweisungen enthält, darf seine eigenen Behauptungen nicht «belegen».
        fields = [f for f in fields if f != "description"]
    evidence = _evidence(product, fields)
    name_text = " ".join(x for x in (product.brand, product.name) if x)
    units = unit_pattern(rules.units)
    evidence_units = {(v, u) for v, u, _ in find_unit_values(evidence, units)}
    evidence_numbers = numbers(evidence) | numbers(name_text) | word_numbers(evidence)
    rating_numbers = set()
    if product.rating:
        rating_numbers = {
            to_decimal(str(product.rating.average)),
            to_decimal(str(product.rating.count)),
        }

    findings: list[Finding] = []
    for field, raw in texts_of(variant):
        text = normalize(raw)
        consumed: list[tuple[int, int]] = []

        # Preise: exakt wie in den Produktdaten dieses Produkts (per ID)
        for value, span in find_prices(text):
            consumed.append(span)
            if product.price is None:
                findings.append(
                    Finding(
                        rule="preis_unbelegt",
                        severity="rot",
                        field=field,
                        message=f"Preis {value} genannt, Produkt hat keinen Preis",
                        source=tag,
                    )
                )
            elif rules.price_must_match_exactly and value != product.price.amount:
                findings.append(
                    Finding(
                        rule="preis_falsch",
                        severity="rot",
                        field=field,
                        message=f"Preis {value} stimmt nicht mit Produkt {product.id} "
                        f"({product.price.currency} {product.price.amount}) überein",
                        source=tag,
                    )
                )

        # Zahlen mit Einheit: müssen in den Belegfeldern stehen (60 h = 60 Std. = 60 Stunden)
        for value, unit, span in find_unit_values(text, units):
            consumed.append(span)
            if (value, unit) not in evidence_units:
                findings.append(
                    Finding(
                        rule="angabe_unbelegt",
                        severity="rot",
                        field=field,
                        message=f"«{text[span[0] : span[1]]}» steht nicht in den Produktdaten "
                        f"von {product.id}",
                        source=tag,
                    )
                )

        # Jede übrige Zahl muss erklärbar sein (Produktname, Bewertung, Produktdaten)
        rest = "".join(
            c if not any(a <= i < b for a, b in consumed) else " " for i, c in enumerate(text)
        )
        for value in numbers(rest):
            if value in evidence_numbers or value in rating_numbers:
                continue
            findings.append(
                Finding(
                    rule="zahl_unbelegt",
                    severity="rot",
                    field=field,
                    message=f"Zahl {value} ist nicht belegt",
                    source=tag,
                )
            )

        # Superlative nur mit Beleg
        claim_text = _without_name(text, product)
        for term in rules.superlatives:
            if term_pattern(term).search(claim_text) and not term_pattern(term).search(evidence):
                findings.append(
                    Finding(
                        rule="superlativ",
                        severity="rot",
                        field=field,
                        message=f"Superlativ «{term}» ohne Beleg",
                        source=tag,
                    )
                )

        # Verbotene Aussagen (nie belegbar)
        for claim in rules.forbidden_claims:
            hits = [t for t in claim.terms if term_pattern(t).search(claim_text)]
            if hits:
                findings.append(
                    Finding(
                        rule=f"verboten:{claim.category}",
                        severity="rot",
                        field=field,
                        message=f"«{hits[0]}» – {claim.reason}",
                        source=tag,
                    )
                )

    # Bewertungsaussagen ohne Bewertungsdaten
    if rules.rating_claims_need_evidence and product.rating is None:
        for field, raw in texts_of(variant):
            if re.search(r"sterne|bewertung|★", raw, re.IGNORECASE):
                findings.append(
                    Finding(
                        rule="bewertung_unbelegt",
                        severity="rot",
                        field=field,
                        message="Bewertungsaussage, aber keine Bewertungsdaten",
                        source=tag,
                    )
                )
    return findings


def _injection_hits(product: Product) -> list[str]:
    text = " ".join(filter(None, [product.description, *product.properties])).lower()
    return [h for h in INJECTION_HINTS if h in text]


def check_suspicious_product_text(product: Product) -> list[Finding]:
    """Hinweis, wenn Produkttext wie eine Anweisung ans Modell aussieht (Prompt-Injection)."""
    hits = _injection_hits(product)
    if not hits:
        return []
    return [
        Finding(
            rule="verdaechtiger_produkttext",
            severity="gelb",
            message=f"Produktdaten von {product.id} enthalten anweisungsartigen Text "
            f"(«{hits[0]}») – Beschreibung zählt nicht als Beleg, Variante genau prüfen",
        )
    ]


# ---------- 4. Markenstimme, deterministischer Teil ----------

SIE_FORM = re.compile(r"(?<![.!?:]\s)(?<!^)\b(Sie|Ihnen|Ihre[mnrs]?|Ihr)\b")


def check_brand_rules(variant: Variant, skill: Skill) -> list[Finding]:
    rules: BrandVoiceRules = skill.rules
    tag = f"markenstimme {skill.version}"
    findings: list[Finding] = []
    for field, raw in texts_of(variant):
        text = normalize(raw)
        for ch in rules.forbidden_characters:
            if ch in text:
                findings.append(
                    Finding(
                        rule="zeichen",
                        severity="rot",
                        field=field,
                        message=f"Verbotenes Zeichen «{ch}»",
                        source=tag,
                    )
                )
        if text.count("!") > rules.max_exclamation_marks:
            findings.append(
                Finding(
                    rule="ausrufezeichen",
                    severity="gelb",
                    field=field,
                    message=f"{text.count('!')} Ausrufezeichen, max. {rules.max_exclamation_marks}",
                    source=tag,
                )
            )
        for phrase in rules.forbidden_phrases:
            if term_pattern(phrase).search(text):
                findings.append(
                    Finding(
                        rule="floskel",
                        severity="rot",
                        field=field,
                        message=f"Verbotene Floskel «{phrase}»",
                        source=tag,
                    )
                )
        if rules.address_form == "du" and SIE_FORM.search(text):
            findings.append(
                Finding(
                    rule="anrede",
                    severity="gelb",
                    field=field,
                    message="Möglicherweise Sie-Form statt Du-Form",
                    source=tag,
                )
            )
        findings += _copied_examples(field, text, rules.examples_not_to_copy, tag)
    return findings


def _copied_examples(field: str, text: str, examples: list[str], tag: str) -> list[Finding]:
    out = []
    tw = words(text)
    for example in examples:
        ew = words(example)
        if not tw or not ew:
            continue
        match = SequenceMatcher(None, tw, ew, autojunk=False).find_longest_match(
            0, len(tw), 0, len(ew)
        )
        if match.size >= 5 or match.size == len(ew):
            severity, kind = "rot", "übernommen"
        elif match.size >= 3:
            severity, kind = "gelb", "teilweise übernommen"
        else:
            continue
        snippet = " ".join(ew[match.b : match.b + match.size])
        out.append(
            Finding(
                rule="beispiel_kopiert",
                severity=severity,
                field=field,
                message=f"Beispiel aus der Markenstimme {kind}: «{snippet}»",
                source=tag,
            )
        )
    return out
