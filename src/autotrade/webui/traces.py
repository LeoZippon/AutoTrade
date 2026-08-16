"""Bounded access to redacted AgentTrace JSONL artifacts."""

from __future__ import annotations

import asyncio
import json
import re
import threading
from collections.abc import AsyncIterator
from pathlib import Path

from autotrade.pipelines.hitl_state import read_status, status_pid_alive

DEFAULT_PAGE_BYTES = 512 * 1024
MAX_TAIL_BYTES = 4 * 1024 * 1024
STREAM_POLL_SECONDS = 1.0
STREAM_IDLE_HEARTBEAT_EVERY = 15
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def resolve_trace_path(experiment_dir: Path, run_id: str | None) -> Path | None:
    """Resolve one canonical trace without accepting paths from client/status data."""

    directory = Path(experiment_dir).resolve()
    if run_id is None:
        status = read_status(directory / "hitl/status.json")
        value = status.get("run_id")
        run_id = str(value) if isinstance(value, str) and value else None
    if run_id is None or not _RUN_ID.fullmatch(run_id):
        return None
    path = (directory / "artifacts/traces" / f"{run_id}.jsonl").resolve()
    trace_root = (directory / "artifacts/traces").resolve()
    return path if path.is_relative_to(trace_root) and path.is_file() else None


def read_initial_prompt(path: Path) -> dict[str, object]:
    """Return the redacted system/user messages recorded at Fold session start."""

    with Path(path).open("rb") as handle:
        for raw in handle:
            event = _decode_event(raw)
            if event.get("event_type") != "session_start":
                continue
            system = event.get("system_prompt")
            instruction = event.get("instruction")
            if not isinstance(system, str) or not isinstance(instruction, str):
                break
            return {
                "run_id": event.get("run_id"),
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": instruction},
                ],
            }
    raise KeyError("trace contains no Fold initial prompt")


def read_trace_page(
    path: Path,
    *,
    offset: int = 0,
    max_bytes: int = DEFAULT_PAGE_BYTES,
) -> dict[str, object]:
    """Read complete events from a byte offset; leave a partial live tail unread."""

    path = Path(path)
    size = path.stat().st_size
    offset = max(0, min(int(offset), size))
    with path.open("rb") as handle:
        handle.seek(offset)
        chunk = handle.read(max(1, int(max_bytes)))
        consumed = chunk.rfind(b"\n") + 1
        if consumed <= 0 and chunk and offset + len(chunk) < size:
            while True:
                more = handle.read(max(1, int(max_bytes)))
                if not more:
                    break
                newline = more.find(b"\n")
                if newline >= 0:
                    next_offset = handle.tell() - len(more) + newline + 1
                    return {
                        "events": [{"raw": f"<oversized event skipped: {next_offset - offset} bytes>"}],
                        "next_offset": next_offset,
                        "eof": next_offset >= size,
                    }
    if consumed <= 0:
        return {
            "events": [],
            "next_offset": offset,
            "eof": offset + len(chunk) >= size and not chunk,
        }
    events = [_decode_event(line) for line in chunk[:consumed].splitlines() if line.strip()]
    next_offset = offset + consumed
    return {"events": events, "next_offset": next_offset, "eof": next_offset >= size}


def read_trace_tail(
    path: Path,
    *,
    max_events: int,
    max_bytes: int = MAX_TAIL_BYTES,
) -> dict[str, object]:
    """Return a bounded tail plus the byte offset where live tailing can resume."""

    path = Path(path)
    size = path.stat().st_size
    if size == 0:
        return {"events": [], "next_offset": 0, "eof": True, "history_truncated": False}
    read_size = min(size, max(1, int(max_bytes)))
    start = size - read_size
    with path.open("rb") as handle:
        handle.seek(start)
        blob = handle.read(read_size)
    if start:
        newline = blob.find(b"\n")
        if newline < 0:
            return {"events": [], "next_offset": size, "eof": True, "history_truncated": True}
        start += newline + 1
        blob = blob[newline + 1 :]
    complete_bytes = blob.rfind(b"\n") + 1
    lines = blob[:complete_bytes].splitlines(keepends=True)
    selected = lines[-max(1, int(max_events)) :]
    events = [_decode_event(line) for line in selected if line.strip()]
    next_offset = start + complete_bytes
    return {
        "events": events,
        "next_offset": next_offset,
        "eof": next_offset >= size,
        "history_truncated": len(selected) < len(lines) or start > 0,
    }


_STATS_CACHE: dict[str, dict[str, object]] = {}
_STATS_LOCK = threading.Lock()


def trace_stats(path: Path) -> dict[str, object]:
    """Incrementally aggregate event/tool/token counts for the operations panel."""

    with _STATS_LOCK:
        path = Path(path)
        size = path.stat().st_size
        key = str(path.resolve())
        cached = _STATS_CACHE.get(key)
        if cached is None or size < int(cached.get("offset", 0)):
            cached = {
                "offset": 0,
                "counts": {},
                "tool_counts": {},
                "llm_total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "active_tool": None,
                "last_event_ts": None,
            }
        offset = int(cached["offset"])
        with path.open("rb") as handle:
            handle.seek(offset)
            blob = handle.read(size - offset)
        tail = blob.rfind(b"\n") + 1
        counts = dict(cached["counts"])
        tool_counts = dict(cached["tool_counts"])
        total = int(cached["llm_total_tokens"])
        prompt = int(cached["prompt_tokens"])
        completion = int(cached["completion_tokens"])
        active_tool = cached.get("active_tool")
        last_ts = cached.get("last_event_ts")
        for raw in blob[:tail].splitlines():
            event = _decode_event(raw)
            kind = str(event.get("event_type") or "event")
            counts[kind] = int(counts.get(kind, 0)) + 1
            last_ts = event.get("ts") or last_ts
            if kind == "tool_call_started":
                active_tool = event.get("tool")
            elif kind == "tool_call":
                tool = str(event.get("tool") or "unknown")
                tool_counts[tool] = int(tool_counts.get(tool, 0)) + 1
                active_tool = None
            elif kind == "llm_call" and isinstance(event.get("usage"), dict):
                usage = event["usage"]
                total += _as_int(usage.get("total_tokens"))
                prompt += _as_int(usage.get("prompt_tokens"))
                completion += _as_int(usage.get("completion_tokens"))
        cached = {
            "offset": offset + tail,
            "counts": counts,
            "tool_counts": tool_counts,
            "llm_total_tokens": total,
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "active_tool": active_tool,
            "last_event_ts": last_ts,
        }
        if len(_STATS_CACHE) >= 32 and key not in _STATS_CACHE:
            _STATS_CACHE.pop(next(iter(_STATS_CACHE)))
        _STATS_CACHE[key] = cached
        return {
            "counts": counts,
            "tool_counts": tool_counts,
            "total_events": sum(int(value) for value in counts.values()),
            "llm_total_tokens": total,
            "llm_prompt_tokens": prompt,
            "llm_completion_tokens": completion,
            "active_tool": active_tool,
            "last_event_ts": last_ts,
            "trace_bytes": size,
        }


async def stream_trace(
    experiment_dir: Path,
    run_id: str | None,
    *,
    offset: int = 0,
) -> AsyncIterator[str]:
    """Replay then tail a trace over SSE without retaining a server-side history."""

    directory = Path(experiment_dir)
    position = max(0, int(offset))
    idle = 0
    yield "retry: 5000\n\n"
    while True:
        path = resolve_trace_path(directory, run_id)
        if path is not None:
            page = read_trace_page(path, offset=position)
            events = page["events"]
            if events:
                position = int(page["next_offset"])
                for event in events[:-1]:
                    yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
                yield f"id: {position}\ndata: {json.dumps(events[-1], ensure_ascii=False, default=str)}\n\n"
                idle = 0
                continue
        status = read_status(directory / "hitl/status.json")
        current = str(status.get("run_id") or "")
        if not status_pid_alive(status) or (run_id is not None and current not in {"", run_id}):
            yield f'event: eof\ndata: {{"offset": {position}}}\n\n'
            return
        if path is None:
            yield 'event: waiting\ndata: {"reason": "trace not started"}\n\n'
        idle += 1
        if idle % STREAM_IDLE_HEARTBEAT_EVERY == 0:
            yield ": keep-alive\n\n"
        await asyncio.sleep(STREAM_POLL_SECONDS)


def _decode_event(raw: bytes) -> dict[str, object]:
    """An unparseable line surfaces verbatim rather than silently vanishing —
    a live trace's partial tail and a corrupted record must both stay visible."""
    text = raw.decode("utf-8", errors="replace").strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}
    return value if isinstance(value, dict) else {"raw": text}


def _as_int(value: object) -> int:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else 0

