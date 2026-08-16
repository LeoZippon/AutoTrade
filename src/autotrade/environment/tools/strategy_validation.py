"""Static validation tool for the sole strategy entrypoint."""

from __future__ import annotations

from collections.abc import Mapping

from autotrade.environment.strategy_loader import (
    StrategyLoadError,
    validate_strategy_source,
)

from .base import ToolError, ToolResult, ToolSpec
from .workspace import SafeWorkspace


class StrategyValidationTool:
    spec = ToolSpec(
        "validate_strategy",
        "Validate syntax, imports, and the generate_orders(context) contract.",
        {
            "type": "object",
            "properties": {"path": {"type": "string", "minLength": 1, "maxLength": 500}},
            "required": ["path"],
            "additionalProperties": False,
        },
    )

    def __init__(self, workspace: SafeWorkspace) -> None:
        self.workspace = workspace

    def invoke(self, arguments: Mapping[str, object]) -> ToolResult:
        path = self.workspace.resolve(str(arguments["path"]), must_exist=True, directory=False)
        try:
            validate_strategy_source(path.read_text(encoding="utf-8"), filename=path.name)
        except StrategyLoadError as exc:
            raise ToolError(str(exc)) from exc
        return ToolResult(True, value={"path": self.workspace.relative(path), "valid": True})


__all__ = ["StrategyValidationTool"]
