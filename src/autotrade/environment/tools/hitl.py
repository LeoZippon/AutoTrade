"""Narrow human-in-the-loop tool exposed only when a hook is injected."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import nullcontext

from autotrade.environment.time_budget import (
    InferenceTimeBudget,
    SessionTimeBudgetAware,
)

from .base import ToolResult, ToolSpec


class AskUserTool(SessionTimeBudgetAware):
    spec = ToolSpec(
        "ask_user",
        "Ask the supervising user one concrete question and wait for the controlled reply.",
        {
            "type": "object",
            "properties": {
                "question": {"type": "string", "minLength": 1, "maxLength": 4_000},
                "summary": {"type": "string", "maxLength": 4_000},
            },
            "required": ["question"],
            "additionalProperties": False,
        },
    )

    def __init__(
        self,
        hook: Callable[[str, str], str],
        *,
        time_budget: InferenceTimeBudget | None = None,
    ) -> None:
        if not callable(hook):
            raise TypeError("ask_user hook must be callable")
        self.hook = hook
        self.time_budget = time_budget

    @property
    def session_time_budget(self) -> InferenceTimeBudget | None:
        return self.time_budget

    def invoke(self, arguments: Mapping[str, object]) -> ToolResult:
        pause = self.time_budget.pause() if self.time_budget is not None else nullcontext()
        with pause:
            reply = self.hook(
                str(arguments["question"]), str(arguments.get("summary") or "")
            )
        return ToolResult(True, value={"reply": str(reply)})


__all__ = ["AskUserTool"]
