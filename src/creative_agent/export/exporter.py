"""Export nur freigegebener Varianten.

- Google Ads Responsive Search Ads: CSV für den Google Ads Editor. Spalten aus der offiziellen
  CSV-Spaltenreferenz (geprüft 2026-11-20):
  https://support.google.com/google-ads/editor/answer/57747
  Eine Spalte «Ad type» dokumentiert die Seite nicht – der Import ist im Ads Editor zu verifizieren.
  Alle Anzeigen starten mit Status «Paused»: Nichts geht ohne aktives Einschalten live.
- Meta: generische CSV (kein offizielles Importformat festgelegt).
- Asset-Paket: PNG je Bildvariante + manifest.json (Herkunft, Gate, Freigabe, SHA-256), als ZIP.
"""

import csv
import hashlib
import json
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel

from ..gate import GateResult
from ..layouts import format_chf
from ..review.store import ReviewState, current_gate, current_variant
from ..workflow.models import RunRecord, Variant

GOOGLE_RSA_COLUMNS = (
    ["Campaign", "Ad group"]
    + [f"Headline {i}" for i in range(1, 16)]
    + [f"Description {i}" for i in range(1, 5)]
    + ["Path 1", "Path 2", "Final URL", "Status", "Labels"]
)
META_COLUMNS = [
    "variant_id",
    "channel",
    "target_group",
    "product_id",
    "product_name",
    "price",
    "primary_text",
    "headline",
    "cta",
    "image_file",
    "final_url",
    "gate_status",
    "approved_at",
]


class ExportError(RuntimeError):
    pass


class ExportResult(BaseModel):
    directory: str
    files: list[str]
    variant_ids: list[str]
    zip_path: str | None


def clean_url(url: str | None) -> str:
    """Entfernt utm_*-Parameter: Die MCP-Links tragen utm_source=shop-mcp, das würde Anzeigen-
    Traffic falsch als KI-Assistenten-Traffic ausweisen."""
    if not url:
        return ""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_")]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def approved_variants(
    record: RunRecord, state: ReviewState, gates: dict[str, GateResult]
) -> list[tuple[Variant, GateResult, str]]:
    """(Variante in aktueller Fassung, Gate, Freigabezeit) – mit Gegenprüfung der Regeln."""
    out = []
    for v in record.variants:
        entry = state.variants.get(v.variant_id)
        if not entry or not entry.decision or entry.decision.decision != "freigegeben":
            continue
        gate = current_gate(gates, state, v.variant_id)
        if gate is None or gate.status == "rot":
            raise ExportError(
                f"{v.variant_id}: freigegeben, aber Gate {gate and gate.status} – "
                "Export abgebrochen"
            )
        if entry.decision.revision != len(entry.revisions):
            raise ExportError(f"{v.variant_id}: Freigabe gilt einer älteren Fassung")
        out.append(
            (
                current_variant(record, state, v.variant_id),
                gate,
                entry.decision.decided_at.isoformat(timespec="seconds"),
            )
        )
    return out


def _png_for(run_dir: Path, state: ReviewState, variant_id: str) -> Path | None:
    entry = state.variants.get(variant_id)
    if entry and entry.revisions and entry.revisions[-1].png_path:
        return Path(entry.revisions[-1].png_path)
    path = run_dir / "assets" / f"{variant_id}.png"
    return path if path.exists() else None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_run(
    record: RunRecord,
    state: ReviewState,
    gates: dict[str, GateResult],
    run_dir: Path,
    *,
    campaign: str | None = None,
) -> ExportResult:
    items = approved_variants(record, state, gates)
    if not items:
        raise ExportError("Keine freigegebene Variante – nichts zu exportieren")
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    out = run_dir / "export" / stamp
    (out / "assets").mkdir(parents=True, exist_ok=True)
    campaign = campaign or f"Creative Automation {record.run_id}"
    files: list[Path] = []
    manifest_items = []

    google_rows, meta_rows = [], []
    for v, gate, approved_at in items:
        product = record.products[v.product_id]
        url = clean_url(product.page_url)
        name = " ".join(x for x in (product.brand, product.name) if x)
        image_file = None
        png = _png_for(run_dir, state, v.variant_id)
        if png is not None and png.exists():
            image_file = f"assets/{v.variant_id}.png"
            shutil.copyfile(png, out / image_file)

        if v.channel == "google_ads_rsa":
            row = {c: "" for c in GOOGLE_RSA_COLUMNS}
            row.update(
                {
                    "Campaign": campaign,
                    "Ad group": f"{name} – {v.target_group}",
                    "Path 1": str(v.fields.get("pfad", "")),
                    "Final URL": url,
                    "Status": "Paused",
                    "Labels": f"creative-automation;{v.variant_id}",
                }
            )
            for i, h in enumerate(v.fields.get("titel", [])[:15], 1):
                row[f"Headline {i}"] = h
            for i, d in enumerate(v.fields.get("beschreibung", [])[:4], 1):
                row[f"Description {i}"] = d
            google_rows.append(row)
        elif v.channel.startswith("meta_"):
            meta_rows.append(
                {
                    "variant_id": v.variant_id,
                    "channel": v.channel,
                    "target_group": v.target_group,
                    "product_id": product.id,
                    "product_name": name,
                    "price": format_chf(product.price.amount) if product.price else "",
                    "primary_text": v.fields.get("primaertext", ""),
                    "headline": v.fields.get("ueberschrift", ""),
                    "cta": v.fields.get("cta", ""),
                    "image_file": image_file or "",
                    "final_url": url,
                    "gate_status": gate.status,
                    "approved_at": approved_at,
                }
            )

        manifest_items.append(
            {
                "variant_id": v.variant_id,
                "channel": v.channel,
                "target_group": v.target_group,
                "product_id": product.id,
                "final_url": url,
                "texts": v.fields,
                "image_file": image_file,
                "image_sha256": _sha256(out / image_file) if image_file else None,
                "gate_status": gate.status,
                "approved_at": approved_at,
                "decision_reason": state.variants[v.variant_id].decision.reason,
                "revision": state.variants[v.variant_id].decision.revision,
            }
        )

    if google_rows:
        files.append(_write_csv(out / "google_ads_rsa.csv", GOOGLE_RSA_COLUMNS, google_rows))
    if meta_rows:
        files.append(_write_csv(out / "meta_ads.csv", META_COLUMNS, meta_rows))
    manifest = {
        "run_id": record.run_id,
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "hinweis": "Private Arbeitsprobe, nicht offiziell von Galaxus. Nicht veröffentlichen.",
        "skills": {s.name: f"{s.version} ({s.content_hash})" for s in record.skills},
        "models": record.models,
        "items": manifest_items,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    files.append(out / "manifest.json")
    files += sorted((out / "assets").glob("*.png"))

    zip_path = out.parent / f"export-{record.run_id}-{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, f.relative_to(out))
    return ExportResult(
        directory=str(out),
        files=[str(f) for f in files],
        variant_ids=[v.variant_id for v, _, _ in items],
        zip_path=str(zip_path),
    )


def _write_csv(path: Path, columns: list[str], rows: list[dict]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path
