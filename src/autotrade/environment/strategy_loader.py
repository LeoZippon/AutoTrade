"""Statically preflight and load a trusted Agent-authored strategy."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

from .strategy import StrategyFunction

ALLOWED_MODULES = frozenset(
    {"__future__", "collections", "datetime", "decimal", "math", "numpy", "pandas", "statistics"}
)
FORBIDDEN_CALLS = frozenset({"compile", "eval", "exec", "open", "__import__"})
FORBIDDEN_ATTRIBUTES = frozenset(
    {
        "read_csv",
        "read_clipboard",
        "read_excel",
        "read_feather",
        "read_fwf",
        "read_gbq",
        "read_hdf",
        "read_html",
        "read_json",
        "read_orc",
        "read_pickle",
        "read_sas",
        "read_sql",
        "read_sql_query",
        "read_sql_table",
        "read_spss",
        "read_stata",
        "read_table",
        "read_xml",
        "fromfile",
        "fromregex",
        "genfromtxt",
        "load",
        "loadtxt",
        "memmap",
        "save",
        "savez",
        "savez_compressed",
        "savetxt",
        "to_csv",
        "to_excel",
        "to_feather",
        "tofile",
        "to_hdf",
        "to_json",
        "to_parquet",
        "to_pickle",
        "to_sql",
        "to_stata",
        "to_xml",
        "urlopen",
    }
)


class StrategyLoadError(RuntimeError):
    pass


def validate_strategy_source(source: str, *, filename: str = "main.py") -> None:
    """Reject common direct capability and external-I/O calls before import.

    This denylist is a convenience check for trusted, reviewed strategies, not
    a sandbox or a security boundary.
    """
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        raise StrategyLoadError(f"invalid strategy syntax: {exc}") from exc
    entrypoints = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "generate_orders"
    ]
    if len(entrypoints) != 1 or isinstance(entrypoints[0], ast.AsyncFunctionDef):
        raise StrategyLoadError("strategy must define exactly one synchronous generate_orders(context)")
    if len(entrypoints[0].args.args) != 1:
        raise StrategyLoadError("generate_orders must accept exactly one context argument")
    context_arg = entrypoints[0].args.args[0].arg
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name.split(".", 1)[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            modules = [str(node.module or "").split(".", 1)[0]]
        else:
            modules = []
        unsupported = sorted(set(modules).difference(ALLOWED_MODULES))
        if unsupported:
            raise StrategyLoadError(f"strategy imports unsupported module: {unsupported[0]}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            raise StrategyLoadError(f"strategy calls forbidden builtin: {node.func.id}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_ATTRIBUTES:
            raise StrategyLoadError(f"strategy calls unsupported external I/O method: {node.func.attr}")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "read_parquet"
            and (not node.args or not _is_context_data_path(node.args[0], context_arg=context_arg))
        ):
            raise StrategyLoadError(
                "strategy may read Parquet only below context.snapshot_dir or context.asof_dir"
            )


def _is_context_data_path(node: ast.AST, *, context_arg: str) -> bool:
    """Recognize a path expression rooted in a read-only context data directory."""

    if isinstance(node, ast.Attribute):
        return (
            isinstance(node.value, ast.Name)
            and node.value.id == context_arg
            and node.attr in {"snapshot_dir", "asof_dir"}
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return (
            _is_context_data_path(node.left, context_arg=context_arg)
            and isinstance(node.right, ast.Constant)
            and isinstance(node.right.value, str)
        )
    return False


def load_strategy(path: str | Path) -> StrategyFunction:
    strategy_path = Path(path).resolve()
    if not strategy_path.is_file():
        raise StrategyLoadError(f"strategy file does not exist: {strategy_path}")
    source = strategy_path.read_text(encoding="utf-8")
    validate_strategy_source(source, filename=strategy_path.name)
    spec = importlib.util.spec_from_file_location("autotrade_user_strategy", strategy_path)
    if spec is None or spec.loader is None:
        raise StrategyLoadError(f"cannot load strategy: {strategy_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise StrategyLoadError(f"strategy import failed: {exc}") from exc
    strategy = getattr(module, "generate_orders", None)
    if not callable(strategy):
        raise StrategyLoadError("strategy does not expose generate_orders")
    return strategy


__all__ = ["StrategyLoadError", "load_strategy", "validate_strategy_source"]
