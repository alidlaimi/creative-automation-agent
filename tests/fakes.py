"""Gescriptetes LLM für Tests: liefert vorbereitete Antworten, zählt Aufrufe, kostet nichts."""

import asyncio
from typing import Any

from creative_agent.workflow.llm import Structured, TokenUsage, ToolTurn

USAGE = TokenUsage(input_tokens=1000, output_tokens=200)


class ScriptedLLM:
    def __init__(
        self,
        structured: list[Any] | None = None,
        tools: list[Any] | None = None,
        delay: float = 0.0,
    ) -> None:
        self.structured_script = list(structured or [])
        self.tool_script = list(tools or [])
        self.delay = delay
        self.structured_calls: list[dict[str, Any]] = []
        self.tool_calls: list[dict[str, Any]] = []

    async def structured(self, *, model, system, messages, output_model, max_tokens):
        self.structured_calls.append(
            {"model": model, "system": system, "messages": messages, "output_model": output_model}
        )
        if self.delay:
            await asyncio.sleep(self.delay)
        item = self.structured_script.pop(0)
        if item == "INVALID":
            return Structured(None, USAGE, "end_turn", error="kaputt")
        return Structured(output_model.model_validate(item), USAGE, "end_turn")

    async def tool_turn(self, *, model, system, messages, tools, tool_choice, max_tokens):
        self.tool_calls.append(
            {
                "model": model,
                "system": system,
                "messages": list(messages),
                "tool_choice": tool_choice,
            }
        )
        blocks = self.tool_script.pop(0)
        return ToolTurn(blocks, USAGE, "tool_use")


def tool_use(name: str, payload: dict, call_id: str = "t1") -> dict:
    return {"type": "tool_use", "id": call_id, "name": name, "input": payload}
