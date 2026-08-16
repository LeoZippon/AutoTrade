"""Container-side JSON-lines worker for one Agent-authored strategy."""

from __future__ import annotations

import contextlib
import json
import os
import sys
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from .strategy import (
    AccountSnapshot,
    StrategyContext,
    StrategyContractError,
    _parse_datetime,
    _validated_strategy_bar,
    _ValidatedStrategyBar,
    _ValidatedStrategyBars,
)
from .strategy_loader import load_strategy


class WorkerProtocolError(RuntimeError):
    pass


class Protocol:
    def __init__(self) -> None:
        self._input = sys.stdin
        # Keep the JSON protocol on a private duplicate of the original stdout
        # pipe, then redirect fd 1 itself to stderr before strategy code loads.
        # This covers Python prints, os.write(1, ...), and native extensions;
        # redirect_stdout alone cannot protect a line-oriented RPC channel.
        protocol_fd = os.dup(sys.stdout.fileno())
        os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
        self._output = os.fdopen(protocol_fd, "w", encoding="utf-8", buffering=1)
        self._active_sequence: int | None = None

    def read(self) -> dict[str, object] | None:
        line = self._input.readline()
        if not line:
            return None
        value = json.loads(line)
        if not isinstance(value, dict):
            raise WorkerProtocolError("protocol message must be a JSON object")
        return value

    def write(self, value: Mapping[str, object]) -> None:
        line = json.dumps(value, ensure_ascii=False, allow_nan=False)
        self._output.write(line + "\n")
        self._output.flush()

    def nl_query(self, request: Mapping[str, object], **_kwargs: object) -> Mapping[str, object]:
        sequence = self._active_sequence
        if sequence is None:
            raise WorkerProtocolError("NL request has no active strategy inference")
        self.write({"type": "nl_request", "sequence": sequence, "request": dict(request)})
        response = self.read()
        if response is None or response.get("type") != "nl_response":
            raise WorkerProtocolError("host did not return an NL response")
        if response.get("sequence") != sequence:
            raise WorkerProtocolError("host NL response sequence does not match request")
        error = response.get("error")
        if error is not None:
            raise WorkerProtocolError(str(error))
        result = response.get("result")
        if not isinstance(result, Mapping):
            raise WorkerProtocolError("host NL response result must be a JSON object")
        return result


_EXECUTE_KEYS = {
    "type",
    "sequence",
    "reset",
    "base_count",
    "total_count",
    "context",
    "bars",
}
_CONTEXT_KEYS = {
    "inference_at",
    "account",
    "snapshot_dir",
    "asof_dir",
    "asof_version",
}


class BarStream:
    """Worker-owned append-only bars, independent of strategy module state."""

    def __init__(self) -> None:
        self._bars = _ValidatedStrategyBars()
        self._sequence = -1
        self._inference_at: datetime | None = None
        self._last_available_at: datetime | None = None

    def context(self, message: Mapping[str, object], protocol: Protocol) -> StrategyContext:
        if set(message) != _EXECUTE_KEYS:
            raise WorkerProtocolError("execute message has missing or unsupported fields")
        sequence = _integer(message.get("sequence"), "sequence")
        base_count = _integer(message.get("base_count"), "base_count")
        total_count = _integer(message.get("total_count"), "total_count")
        reset = message.get("reset")
        if not isinstance(reset, bool):
            raise WorkerProtocolError("reset must be a boolean")
        if reset:
            if sequence != 0 or base_count != 0:
                raise WorkerProtocolError("reset execute must start at sequence=0 and base_count=0")
            previous_bars = _ValidatedStrategyBars()
            previous_inference = None
            previous_available_at = None
        else:
            if self._sequence < 0:
                raise WorkerProtocolError("first execute message must reset the bar stream")
            if sequence != self._sequence + 1:
                raise WorkerProtocolError("execute sequence is not contiguous")
            if base_count != len(self._bars):
                raise WorkerProtocolError("base_count does not match worker bar state")
            previous_bars = self._bars
            previous_inference = self._inference_at
            previous_available_at = self._last_available_at

        raw_context = message.get("context")
        if not isinstance(raw_context, dict) or set(raw_context) != _CONTEXT_KEYS:
            raise WorkerProtocolError("execute context has missing or unsupported fields")
        inference_at = _parse_datetime(raw_context.get("inference_at"), "inference_at")
        if previous_inference is not None and inference_at <= previous_inference:
            raise WorkerProtocolError("inference_at must increase monotonically")
        raw_delta = message.get("bars")
        if not isinstance(raw_delta, list):
            raise WorkerProtocolError("execute bars must be a JSON array")
        if total_count != base_count + len(raw_delta):
            raise WorkerProtocolError("total_count does not equal base_count plus delta")

        delta: list[_ValidatedStrategyBar] = []
        last_available_at = previous_available_at
        for raw in raw_delta:
            try:
                bar = _validated_strategy_bar(
                    raw,
                    inference_at=inference_at,
                    decoded_json=True,
                )
            except StrategyContractError as exc:
                raise WorkerProtocolError(str(exc)) from exc
            if last_available_at is not None and bar._available_at < last_available_at:
                raise WorkerProtocolError("bar available_at must be monotonic")
            delta.append(bar)
            last_available_at = bar._available_at
        bars = _ValidatedStrategyBars(
            (*previous_bars, *delta),
            max_available_at=last_available_at,
            available_at_monotonic=True,
        )
        if len(bars) != total_count:
            raise WorkerProtocolError("worker bar state does not match total_count")

        try:
            context = StrategyContext(
                inference_at=inference_at,
                bars=bars,
                account=AccountSnapshot.from_record(raw_context.get("account")),
                snapshot_dir=raw_context.get("snapshot_dir"),  # type: ignore[arg-type]
                asof_dir=raw_context.get("asof_dir"),  # type: ignore[arg-type]
                asof_version=raw_context.get("asof_version"),  # type: ignore[arg-type]
                _nl_query=protocol.nl_query,
            )
        except StrategyContractError as exc:
            raise WorkerProtocolError(str(exc)) from exc

        self._bars = bars
        self._sequence = sequence
        self._inference_at = inference_at
        self._last_available_at = last_available_at
        return context


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise WorkerProtocolError(f"{name} must be a non-negative integer")
    return value


def run(strategy_path: str | Path) -> int:
    protocol = Protocol()
    stream = BarStream()
    try:
        with contextlib.redirect_stdout(sys.stderr):
            strategy = load_strategy(strategy_path)
    except Exception as exc:  # noqa: BLE001 - report import failures through the protocol
        protocol.write({"type": "error", "error": f"strategy import failed: {exc}"})
        return 1
    while True:
        message: dict[str, object] | None = None
        try:
            message = protocol.read()
            if message is None or message.get("type") == "close":
                return 0
            if message.get("type") != "execute":
                raise WorkerProtocolError("expected execute message")
            context = stream.context(message, protocol)
            sequence = message["sequence"]
            protocol._active_sequence = sequence  # worker-private protocol state
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    orders = strategy(context)
            finally:
                protocol._active_sequence = None
            protocol.write({"type": "orders", "sequence": sequence, "orders": orders})
        except Exception as exc:  # noqa: BLE001 - isolate each untrusted strategy call
            error: dict[str, object] = {"type": "error", "error": str(exc)}
            if isinstance(message, Mapping):
                sequence = message.get("sequence")
                if isinstance(sequence, int) and not isinstance(sequence, bool):
                    error["sequence"] = sequence
            protocol.write(error)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -m autotrade.environment.strategy_worker STRATEGY.py", file=sys.stderr)
        return 2
    return run(args[0])


if __name__ == "__main__":
    raise SystemExit(main())
