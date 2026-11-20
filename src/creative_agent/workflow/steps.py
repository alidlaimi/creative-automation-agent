"""Die drei Schritte: Briefing lesen → Produkte recherchieren (agentisch) → Varianten schreiben."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, create_model

from ..mcp_client import GalaxusProductSearch, MCPDataError, MCPToolError, Product
from ..mcp_client.client import SearchArgumentError
from ..skills import Skill
from ..skills.models import Channel, ChannelFormatsRules
from . import prompts
from .budget import CostTracker
from .llm import LLM
from .models import BriefingSpec, ProductChoice, SearchLog, Variant


class WorkflowError(RuntimeError):
    pass


@dataclass
class StepContext:
    llm: LLM
    tracker: CostTracker
    model: str
    model_fast: str


async def structured_with_retry(
    ctx: StepContext,
    *,
    step: str,
    model: str,
    system: str,
    prompt: str,
    output_model: type[BaseModel],
    validate: Callable[[Any], list[str]],
    max_tokens: int,
    attempts: int = 3,
) -> Any:
    """Strukturierter Aufruf; bei Schema- oder Inhaltsfehlern Wiederholung mit Fehlerhinweis."""
    feedback: list[str] = []
    for _ in range(attempts):
        ctx.tracker.check()
        content = prompt
        if feedback:
            content += "\n\nDein letzter Versuch war ungültig:\n- " + "\n- ".join(feedback)
            content += "\nKorrigiere genau diese Punkte."
        result = await ctx.llm.structured(
            model=model,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_model=output_model,
            max_tokens=max_tokens,
        )
        ctx.tracker.add(step, model, result.usage)
        if result.stop_reason == "refusal":
            raise WorkflowError(f"{step}: Modell hat die Anfrage abgelehnt")
        if result.parsed is None:
            feedback = [f"Antwort passt nicht zum Schema: {result.error}"]
            if result.stop_reason == "max_tokens":
                feedback.append("Antwort wurde abgeschnitten – fasse dich kürzer.")
            continue
        feedback = validate(result.parsed)
        if not feedback:
            return result.parsed
    raise WorkflowError(f"{step}: nach {attempts} Versuchen ungültig: {feedback}")


# ---------- 1. Briefing ----------


async def parse_briefing(
    ctx: StepContext, briefing_text: str, channels: ChannelFormatsRules
) -> BriefingSpec:
    allowed = set(channels.channels)

    def validate(spec: BriefingSpec) -> list[str]:
        errors = [f"Unbekannter Kanal {c!r}" for c in spec.channels if c not in allowed]
        if not spec.channels:
            errors.append("Mindestens ein Kanal nötig")
        if not spec.target_groups:
            errors.append("Mindestens eine Zielgruppe nötig")
        if spec.min_price_chf and spec.max_price_chf and spec.min_price_chf > spec.max_price_chf:
            errors.append("min_price_chf ist grösser als max_price_chf")
        return errors

    spec = await structured_with_retry(
        ctx,
        step="briefing",
        model=ctx.model_fast,
        system=prompts.briefing_system(channels.channels),
        prompt=f"Briefing:\n{briefing_text}",
        output_model=BriefingSpec,
        validate=validate,
        max_tokens=1000,
    )
    return spec.model_copy(update={"channels": list(dict.fromkeys(spec.channels))})


# ---------- 2. Recherche (agentisch) ----------

SEARCH_TOOL = {
    "name": "search_products",
    "description": "Sucht im Galaxus-Sortiment (Schweiz). Liefert Produkte mit ID, Preis, "
    "Eigenschaften und Bewertungen. Preise als ganze CHF.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Suchbegriff"},
            "min_price": {"type": ["integer", "null"], "description": "CHF oder null"},
            "max_price": {"type": ["integer", "null"], "description": "CHF oder null"},
        },
        "required": ["query", "min_price", "max_price"],
        "additionalProperties": False,
    },
}

SELECT_TOOL = {
    "name": "select_products",
    "description": "Schliesst die Recherche ab: gewählte Produkt-IDs mit Begründung.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "choices": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "product_id": {"type": "string"},
                        "reason": {"type": "string", "description": "Ein Satz"},
                    },
                    "required": ["product_id", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["choices"],
        "additionalProperties": False,
    },
}


@dataclass
class ResearchResult:
    searches: list[SearchLog]
    products: dict[str, Product]
    selection: list[ProductChoice]
    completed_by: str  # "agent" oder "strukturierter_abschluss"


async def research_products(
    ctx: StepContext,
    spec: BriefingSpec,
    search: GalaxusProductSearch,
    *,
    max_searches: int = 3,
    max_products: int = 3,
    results_per_search: int = 10,
) -> ResearchResult:
    seen: dict[str, Product] = {}
    searches: list[SearchLog] = []
    user_intent = f"{spec.campaign_goal} – Zielgruppe: {', '.join(spec.target_groups)}"[:200]
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                f"Briefing: {spec.campaign_goal}\n"
                f"Zielgruppen: {', '.join(spec.target_groups)}\n"
                f"Vorschlag Suchbegriff: {spec.product_query}\n"
                f"Preisrahmen CHF: {spec.min_price_chf or '-'} bis {spec.max_price_chf or '-'}\n"
                f"Kanäle: {', '.join(spec.channels)}"
            ),
        }
    ]
    # Neuere Modelle (u.a. Sonnet 5.5) lehnen erzwungene Tool-Wahl ("any"/"tool") mit 400 ab.
    # Daher immer "auto" + strict tools; wählt das Modell nicht selbst, schliesst ein
    # strukturierter Aufruf die Auswahl garantiert ab.
    max_turns = max_searches + 2
    for _ in range(max_turns):
        ctx.tracker.check()
        reply = await ctx.llm.tool_turn(
            model=ctx.model,
            system=prompts.research_system(max_searches, max_products),
            messages=messages,
            tools=[SEARCH_TOOL, SELECT_TOOL],
            tool_choice={"type": "auto"},
            max_tokens=1500,
        )
        ctx.tracker.add("recherche", ctx.model, reply.usage)
        messages.append({"role": "assistant", "content": reply.blocks})

        results: list[dict[str, Any]] = []
        for block in reply.blocks:
            if block["type"] != "tool_use":
                continue
            args = block["input"]
            if block["name"] == "search_products":
                text, is_error = await _run_search(
                    search,
                    args,
                    spec,
                    user_intent,
                    searches,
                    seen,
                    max_searches,
                    results_per_search,
                )
            elif block["name"] == "select_products":
                choices, problems = _check_selection(args, seen, max_products)
                if not problems:
                    return ResearchResult(searches, seen, choices, "agent")
                text, is_error = "Auswahl ungültig: " + "; ".join(problems), True
            else:
                text, is_error = f"Unbekanntes Tool {block['name']}", True
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": text,
                    "is_error": is_error,
                }
            )
        if results:
            messages.append({"role": "user", "content": results})
        else:
            messages.append(
                {"role": "user", "content": "Bitte rufe search_products oder select_products auf."}
            )

    if not seen:
        raise WorkflowError("Recherche ohne Suchergebnisse beendet")
    choices = await _structured_selection(ctx, spec, seen, max_products)
    return ResearchResult(searches, seen, choices, "strukturierter_abschluss")


class SelectionOutput(BaseModel):
    choices: list[ProductChoice] = Field(description="1 bis 3 Produkte mit Begründung")


async def _structured_selection(
    ctx: StepContext, spec: BriefingSpec, seen: dict[str, Product], max_products: int
) -> list[ProductChoice]:
    def validate(out: SelectionOutput) -> list[str]:
        _, problems = _check_selection(
            {"choices": [c.model_dump() for c in out.choices]}, seen, max_products
        )
        return problems

    out = await structured_with_retry(
        ctx,
        step="recherche:abschluss",
        model=ctx.model,
        system=prompts.research_system(0, max_products),
        prompt=(
            f"Briefing: {spec.campaign_goal}\nZielgruppen: {', '.join(spec.target_groups)}\n"
            f"Wähle aus diesen Suchergebnissen:\n{prompts.wrap_products(list(seen.values()))}"
        ),
        output_model=SelectionOutput,
        validate=validate,
        max_tokens=1500,
    )
    return out.choices


async def _run_search(search, args, spec, user_intent, searches, seen, max_searches, first):
    if len(searches) >= max_searches:
        return "Suchlimit erreicht. Wähle jetzt mit select_products aus.", True
    try:
        result = await search.search(
            args["query"],
            language=spec.language if spec.language in ("de", "fr", "it", "en") else "de",
            first=first,
            min_price=args.get("min_price"),
            max_price=args.get("max_price"),
            user_intent=user_intent,
        )
    except (SearchArgumentError, MCPToolError, MCPDataError) as exc:
        return f"Suche fehlgeschlagen: {exc}", True
    for p in result.products:
        seen[p.id] = p
    searches.append(
        SearchLog(
            query=result.query,
            min_price=args.get("min_price"),
            max_price=args.get("max_price"),
            total_count=result.total_count,
            product_ids=[p.id for p in result.products],
        )
    )
    if not result.products:
        return (
            f"Keine Treffer ({result.error_message or 'leer'}). Anderen Begriff versuchen.",
            False,
        )
    header = f"{result.total_count} Treffer, die ersten {len(result.products)}:\n"
    return header + prompts.wrap_products(list(result.products)), False


def _check_selection(args, seen, max_products) -> tuple[list[ProductChoice], list[str]]:
    raw = args.get("choices") or []
    problems = []
    if not 1 <= len(raw) <= max_products:
        problems.append(f"1 bis {max_products} Produkte wählen (gewählt: {len(raw)})")
    choices = []
    for item in raw:
        pid = str(item.get("product_id", "")).strip()
        if pid not in seen:
            problems.append(f"ID {pid!r} kam in keinem Suchergebnis vor")
        elif any(c.product_id == pid for c in choices):
            problems.append(f"ID {pid} doppelt")
        else:
            choices.append(ProductChoice(product_id=pid, reason=str(item.get("reason", ""))))
    return choices, problems


# ---------- 3. Varianten ----------


def variant_models(channel_id: str, channel: Channel) -> tuple[type[BaseModel], type[BaseModel]]:
    """Ausgabeschema dynamisch aus dem Skill 'kanalformate': neuer Kanal = kein neuer Code."""
    fields: dict[str, Any] = {
        "product_id": (str, Field(description="ID eines ausgewählten Produkts")),
        "idee": (str, Field(description="Kreative Idee der Variante in einem Satz")),
    }
    for key, spec in channel.text_fields.items():
        multi = spec.max_count is not None and int(spec.max_count.value) > 1
        desc = spec.label
        if spec.max_chars:
            desc += f", je max. {spec.max_chars.value} Zeichen"
        if multi:
            lo = int(spec.min_count.value) if spec.min_count else 1
            desc += f", {lo} bis {spec.max_count.value} Einträge"
        fields[key] = (list[str] if multi else str, Field(description=desc))
    required = channel.required_elements.value if channel.required_elements else []
    if "cta" in required:
        fields["cta"] = (str, Field(description="Call-to-Action, 1–3 Wörter, z.B. 'Ansehen'"))
    single = create_model(f"Variante_{channel_id}", **fields)
    many = create_model(
        f"Varianten_{channel_id}", varianten=(list[single], Field(description="Varianten"))
    )
    return single, many


async def write_variants(
    ctx: StepContext,
    *,
    spec: BriefingSpec,
    channel_id: str,
    channel: Channel,
    target_group: str,
    products: list[Product],
    brand_voice: Skill,
    fact_check: Skill,
    count: int,
    id_prefix: str,
) -> list[Variant]:
    _, many = variant_models(channel_id, channel)
    allowed_ids = {p.id for p in products}

    def validate(result: Any) -> list[str]:
        errors = []
        if len(result.varianten) < count:
            errors.append(f"{count} Varianten verlangt, {len(result.varianten)} geliefert")
        for i, v in enumerate(result.varianten, 1):
            if v.product_id not in allowed_ids:
                errors.append(f"Variante {i}: product_id {v.product_id!r} nicht ausgewählt")
        return errors

    prompt = (
        f"Kampagnenziel: {spec.campaign_goal}\n"
        f"Zielgruppe: {target_group}\n"
        f"Sprache: {spec.language}\n"
        f"{prompts.channel_brief(channel_id, channel)}\n\n"
        f"Schreibe {count} unterschiedliche Varianten (verschiedene Ideen, gern verschiedene "
        "Produkte aus der Auswahl).\n\n"
        f"{prompts.wrap_products(products)}"
    )
    result = await structured_with_retry(
        ctx,
        step=f"varianten:{channel_id}",
        model=ctx.model,
        system=prompts.copy_system(brand_voice, fact_check),
        prompt=prompt,
        output_model=many,
        validate=validate,
        max_tokens=4000,
    )
    variants = []
    for i, v in enumerate(result.varianten[:count], 1):
        data = v.model_dump()
        texts = {k: data[k] for k in data if k not in ("product_id", "idee")}
        variants.append(
            Variant(
                variant_id=f"{id_prefix}-{i}",
                channel=channel_id,
                target_group=target_group,
                product_id=v.product_id,
                idea=v.idee,
                fields=texts,
            )
        )
    return variants


def selection_products(selection: list[ProductChoice], seen: dict[str, Product]) -> list[Product]:
    return [seen[c.product_id] for c in selection]


__all__ = [
    "ResearchResult",
    "StepContext",
    "WorkflowError",
    "parse_briefing",
    "research_products",
    "selection_products",
    "variant_models",
    "write_variants",
]
