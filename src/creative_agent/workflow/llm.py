"""Dünne Schicht über der Claude API.

Der Workflow kennt nur das Protokoll `LLM`. In Tests ersetzt ein gescriptetes LLM die API –
so laufen alle Tests ohne Netz und ohne Kosten.
"""

from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0

    @property
    def total_input(self) -> int:
        return self.input_tokens + self.cache_creation_input_tokens + self.cache_read_input_tokens


@dataclass(frozen=True)
class ToolTurn:
    blocks: list[dict[str, Any]]  # Inhalt der Assistant-Nachricht (text / tool_use)
    usage: TokenUsage
    stop_reason: str | None


@dataclass(frozen=True)
class Structured:
    parsed: BaseModel | None  # None, wenn die Antwort nicht zum Schema passt
    usage: TokenUsage
    stop_reason: str | None
    error: str | None = None


class LLM(Protocol):
    async def tool_turn(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_choice: dict[str, Any],
        max_tokens: int,
    ) -> ToolTurn: ...

    async def structured(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        output_model: type[BaseModel],
        max_tokens: int,
    ) -> Structured: ...


def _usage(raw: Any) -> TokenUsage:
    return TokenUsage(
        input_tokens=raw.input_tokens or 0,
        output_tokens=raw.output_tokens or 0,
        cache_creation_input_tokens=raw.cache_creation_input_tokens or 0,
        cache_read_input_tokens=raw.cache_read_input_tokens or 0,
    )


class AnthropicLLM:
    def __init__(self, api_key: str, timeout_seconds: float = 60, max_retries: int = 2) -> None:
        from anthropic import AsyncAnthropic

        # max_retries: SDK wiederholt bei Netzwerkfehlern, 429 und 5xx automatisch.
        self._client = AsyncAnthropic(
            api_key=api_key, timeout=timeout_seconds, max_retries=max_retries
        )

    async def tool_turn(self, *, model, system, messages, tools, tool_choice, max_tokens):
        resp = await self._client.messages.create(
            model=model,
            system=system,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            max_tokens=max_tokens,
        )
        blocks: list[dict[str, Any]] = []
        for b in resp.content:
            if b.type == "text":
                blocks.append({"type": "text", "text": b.text})
            elif b.type == "tool_use":
                blocks.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
        return ToolTurn(blocks, _usage(resp.usage), resp.stop_reason)

    async def structured(self, *, model, system, messages, output_model, max_tokens):
        # Bewusst create() statt parse(): parse() wirft bei ungültiger Antwort eine Ausnahme,
        # und die Token-Zahlen (= Kosten) gingen verloren. So wird jeder Aufruf gezählt.
        from anthropic import transform_schema

        schema = transform_schema(output_model.model_json_schema())
        resp = await self._client.messages.create(
            model=model,
            system=system,
            messages=messages,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            max_tokens=max_tokens,
        )
        usage = _usage(resp.usage)
        text = "".join(b.text for b in resp.content if b.type == "text")
        try:
            return Structured(output_model.model_validate_json(text), usage, resp.stop_reason)
        except ValidationError as exc:
            return Structured(None, usage, resp.stop_reason, error=str(exc)[:1500])
