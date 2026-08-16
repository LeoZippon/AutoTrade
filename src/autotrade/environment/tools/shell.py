"""Isolated-shell tool; it cannot execute a host subprocess."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from .base import CommandRunner, ToolError, ToolResult, ToolSpec
from .workspace import SafeWorkspace

# Advisory (not enforced): nudge the Agent away from hiding stderr, which breaks audit.
STDERR_SUPPRESSION_RE = re.compile(r"2\s*>\s*/dev/null|&>\s*/dev/null|/dev/null\s+2\s*>\s*&\s*1")
STDERR_SUPPRESSION_REMINDER = (
    "stderr 被重定向到 /dev/null：错误输出对审计与调试很重要，请保留 stderr（去掉 2>/dev/null 等）。"
)
READ_ONLY_COMMANDS = {
    "awk",
    "cat",
    "cut",
    "du",
    "file",
    "find",
    "grep",
    "head",
    "jq",
    "less",
    "ls",
    "nl",
    "pwd",
    "rg",
    "sort",
    "stat",
    "tail",
    "wc",
}
SEARCH_COMMANDS = {"ag", "ack", "find", "grep", "locate", "rg", "which", "whereis"}
LIST_COMMANDS = {"du", "ls", "tree"}
SHELL_NEUTRAL_COMMANDS = {"echo", "printf", "true", "false", ":"}
WRITE_COMMANDS = {
    "apply_patch",
    "chmod",
    "chown",
    "cp",
    "dd",
    "install",
    "ln",
    "mkdir",
    "mv",
    "rm",
    "rmdir",
    "tee",
    "touch",
    "truncate",
}


class SandboxShellTool:
    spec = ToolSpec(
        "shell",
        "Run an argv command in the injected network-disabled Agent sandbox.",
        {
            "type": "object",
            "properties": {
                "argv": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1, "maxLength": 1000},
                },
                "cwd": {"type": "string", "minLength": 1, "maxLength": 500},
                "timeout_seconds": {"type": "number", "minimum": 0.1, "maximum": 120},
                "input": {"type": "string", "maxLength": 100_000},
            },
            "required": ["argv"],
            "additionalProperties": False,
        },
        mutating=True,
    )

    def __init__(
        self,
        workspace: SafeWorkspace,
        runner: CommandRunner,
        *,
        timeout_seconds: float = 30.0,
        max_output_chars: int = 40_000,
    ) -> None:
        if timeout_seconds <= 0 or max_output_chars <= 0:
            raise ValueError("shell limits must be positive")
        self.workspace = workspace
        self.runner = runner
        self.timeout_seconds = timeout_seconds
        self.max_output_chars = max_output_chars

    def invoke(self, arguments: Mapping[str, object]) -> ToolResult:
        raw_argv = arguments["argv"]
        if not isinstance(raw_argv, list) or not raw_argv:
            raise ToolError("argv must contain at least one argument")
        argv: Sequence[str] = tuple(str(item) for item in raw_argv)
        requested_cwd = str(arguments.get("cwd", "."))
        cwd = self.workspace.resolve(requested_cwd, must_exist=True, directory=True)
        requested_timeout = float(arguments.get("timeout_seconds", self.timeout_seconds))
        timeout = min(requested_timeout, self.timeout_seconds)
        result = self.runner.run(
            argv,
            cwd=self.workspace.relative(cwd) if cwd != self.workspace.root else ".",
            timeout_seconds=timeout,
            max_output_chars=self.max_output_chars,
            input_text=str(arguments["input"]) if "input" in arguments else None,
        )
        record = result.to_record()
        # Audit statistics only; permissions stay with the sandbox, the
        # filesystem and the tool registry's post-finish write lock.
        record["command_kind"] = _classify_command(argv)
        reminder = _stderr_suppression_reminder(argv)
        if reminder:
            record["stderr_suppression_reminder"] = reminder
        return ToolResult(True, value=record)


class ReadOnlyShellTool(SandboxShellTool):
    """Shell surface for Explore with a small non-executing command allowlist."""

    spec = ToolSpec(
        "shell",
        "Run one allowlisted read-only command in the network-disabled sandbox.",
        SandboxShellTool.spec.input_schema,
    )
    _COMMANDS = frozenset(
        {"cat", "cut", "du", "grep", "head", "ls", "pwd", "readlink", "realpath", "rg", "stat", "tail", "tr", "uniq", "wc"}
    )

    def invoke(self, arguments: Mapping[str, object]) -> ToolResult:
        raw_argv = arguments.get("argv")
        if not isinstance(raw_argv, list) or not raw_argv:
            raise ToolError("argv must contain at least one argument")
        command = str(raw_argv[0])
        if command not in self._COMMANDS:
            raise ToolError(f"read-only shell command is not allowed: {command}")
        if command == "rg" and any(
            argument in {"--pre", "--hostname-bin"}
            or argument.startswith(("--pre=", "--hostname-bin="))
            for argument in map(str, raw_argv[1:])
        ):
            raise ToolError("read-only rg cannot execute helper programs")
        return super().invoke(arguments)


def _classify_command(tokens: Sequence[str]) -> str:
    """Best-effort audit label only; permissions are enforced by Docker/filesystem."""
    words = [_basename(token) for token in tokens if token and not token.startswith("-")]
    if not words:
        return "unknown"
    meaningful = [word for word in words if word not in SHELL_NEUTRAL_COMMANDS]
    if not meaningful:
        return "neutral"
    first = meaningful[0]
    if first in WRITE_COMMANDS:
        return "write"
    if first in SEARCH_COMMANDS:
        return "search"
    if first in LIST_COMMANDS:
        return "list"
    if first in READ_ONLY_COMMANDS:
        return "read"
    return "unknown"


def _stderr_suppression_reminder(tokens: Sequence[str]) -> str | None:
    """Advisory when the command redirects stderr away; never blocks the call.

    The argv contract keeps redirections out of the shell's own parsing, but an
    Agent can still reach one through ``bash -lc "... 2>/dev/null"``, so the
    whole command line is scanned.
    """
    return STDERR_SUPPRESSION_REMINDER if STDERR_SUPPRESSION_RE.search(" ".join(tokens)) else None


def _basename(token: str) -> str:
    return token.rstrip("/").rsplit("/", 1)[-1]


__all__ = ["ReadOnlyShellTool", "SandboxShellTool"]
