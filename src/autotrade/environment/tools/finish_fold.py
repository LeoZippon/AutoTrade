"""Select one immutable, fully evaluated Step as the Fold result."""

from __future__ import annotations

from collections.abc import Mapping

from autotrade.environment.step_tree import StepTree

from .base import ToolError, ToolResult, ToolSpec


class FinishFoldTool:
    spec = ToolSpec(
        "finish_fold",
        "Finish this Fold with a fully evaluated Step revision.",
        {
            "type": "object",
            "properties": {"node_id": {"type": "string", "minLength": 1, "maxLength": 500}},
            "required": [],
            "additionalProperties": False,
        },
    )

    def __init__(self, tree: StepTree, *, fold_id: str, run_id: str) -> None:
        self.tree = tree
        self.fold_id = fold_id
        self.run_id = run_id

    def invoke(self, arguments: Mapping[str, object]) -> ToolResult:
        node_id = str(arguments.get("node_id") or self.tree.current_node_id or "")
        if not node_id:
            raise ToolError("finish_fold requires a fully evaluated Step")
        node = self.tree.get_node(node_id)
        if node.get("fold_id") != self.fold_id or node.get("run_id") != self.run_id:
            raise ToolError("finish_fold can select only a Step from the current Fold session")
        if not node.get("complete_validation") or not node.get("revision_id"):
            raise ToolError("finish_fold requires successful complete validation")
        self.tree.set_position(node_id)
        return ToolResult(
            True,
            value={
                "node_id": node_id,
                "revision_id": str(node["revision_id"]),
                "status": "fold_finished",
                # Candidate selection, AcceptanceRules and the final freeze are
                # the Pipeline's, not the Agent's: finishing only nominates.
                "fold_status": "pending_pipeline_review",
                "write_locked": True,
            },
            finish=True,
        )


__all__ = ["FinishFoldTool"]
