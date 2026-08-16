"""Host-side NL Sub Agent with point-in-time text retrieval.

``ctx.nl(...)`` starts one bounded host-side Sub Agent task. The Sub Agent may
call the ``text_retrieve`` tool, which is backed by the snapshot text index and
``text_library/``. Answers are free-form by default; an optional enum response
contract gives narrow strategy decisions a cheaper, bounded path with a
canonical result.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from autotrade.environment.llm.proxy import (
    ChatMessage,
    LLMProxy,
    LLMProxyError,
    ProviderResponse,
    ToolCall,
)
from autotrade.environment.nl.retrieval import TextRetriever
from autotrade.environment.runtime import new_id, sanitize_for_log, utc_now_iso
from autotrade.environment.tools.base import ToolSpec

MAX_TOOL_ROUNDS = 3
# Compatible providers may count hidden reasoning against this cap when they do
# not support the per-call override; 128 can end before a one-word label appears.
ENUM_MAX_TOKENS = 512
ENUM_MAX_RESULTS = 5
ENUM_SNIPPET_CHARS = 1000
TEXT_RETRIEVE_TOOL = "text_retrieve"

TEXT_RETRIEVE_SPEC = ToolSpec(
    TEXT_RETRIEVE_TOOL,
    (
        "Retrieve point-in-time text evidence by case-insensitive grep/regex over titles, "
        "codes, and optional full text bodies. RE2 semantics: backreferences and "
        "lookaround are unsupported; patterns are capped at 256 chars."
    ),
    {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "minLength": 1,
                "maxLength": 256,
                "description": "Case-insensitive grep/regex pattern (RE2 semantics).",
            },
            "ts_code": {
                "type": "string",
                "description": (
                    "Optional stock code that bounds retrieval to code/name-linked candidate "
                    "evidence; leave empty for event, sector, macro, or market-wide searches."
                ),
            },
            "max_results": {"type": "integer", "minimum": 1, "maximum": 20},
            "search_bodies": {"type": "boolean"},
        },
        "required": ["pattern"],
        "additionalProperties": False,
    },
)

SUB_AGENT_SYSTEM_PROMPT = """\
# Role
You are an A-share point-in-time natural-language research Sub Agent. You help
strategy code answer the user's prompt for one stock, event, sector, macro, or
decision context.

# Data Boundary
Use only the context and text evidence returned by tools in this task. Do not
use future events, price moves after the decision time, private credentials, or
unstated facts from memory. Prefer the most recent point-in-time evidence, and
remember publish/ingest time and retrieval recall are imperfect. If the evidence
is thin or absent, say so explicitly and lower your confidence instead of filling
gaps with model priors; treat free text as evidence to weigh, not an established
fact.

# Available Tool
Call the ``text_retrieve`` function tool (native function calling) to fetch text
evidence. ``pattern`` uses case-insensitive grep/regex semantics (RE2 engine:
backreferences and lookaround are unsupported; max 256 chars — an out-of-contract
pattern returns a fixable tool error) over titles, codes, and optional full text
bodies. A single-stock request is already bounded to code/name-linked evidence,
so search its event/risk concepts directly; use broad event/sector/macro patterns
for general requests. Optional arguments:
``ts_code``, ``max_results`` (1-20), ``search_bodies``. ``ts_code`` bounds a
single-stock search to code/name-linked evidence; omit it for broad context.

# Final Answer
If the request includes ``response_contract``, return exactly one listed value
and no other text. Otherwise answer in any format useful to the calling strategy:
plain text, JSON, bullet points, a numeric rubric, or a short decision note are
all allowed. Do not fabricate evidence identifiers.
"""

FINAL_AFTER_TOOL_BUDGET = (
    "The text retrieval budget for this NL Sub Agent task is exhausted. "
    "Return your final answer now in any format. Do not request more tools."
)


@dataclass(frozen=True)
class NLSubAgentConfig:
    max_tokens: int = 3000
    max_tool_rounds: int = MAX_TOOL_ROUNDS
    # ``fail`` makes the caller fail the backtest. ``return_error_with_audit``
    # returns an auditable result dict with status=error so Agent code can
    # decide how to handle unavailable text analysis.
    failure_policy: str = "fail"
    # Absolute monotonic deadline shared with the calling decision: the loop
    # stops before a round that cannot finish inside it, so an in-flight NL task
    # cannot stretch a decision far past its wall cap.
    deadline_at: float | None = None
    response_choices: tuple[str, ...] = ()
    max_results_per_search: int | None = None
    max_evidence_snippet_chars: int | None = None
    lookback_days: int | None = None

    def __post_init__(self) -> None:
        if self.max_tool_rounds < 0:
            raise ValueError("max_tool_rounds must be non-negative")
        if self.max_results_per_search is not None and self.max_results_per_search <= 0:
            raise ValueError("max_results_per_search must be positive")
        if (
            self.max_evidence_snippet_chars is not None
            and self.max_evidence_snippet_chars <= 0
        ):
            raise ValueError("max_evidence_snippet_chars must be positive")
        if self.lookback_days is not None and (
            isinstance(self.lookback_days, bool)
            or not isinstance(self.lookback_days, int)
            or self.lookback_days <= 0
        ):
            raise ValueError("lookback_days must be a positive integer")
        if self.failure_policy not in {"fail", "return_error_with_audit"}:
            raise ValueError(f"unsupported failure_policy={self.failure_policy}")


@dataclass
class NLSubAgentResult:
    ts_code: str
    task_id: str
    state: str
    content: str = ""
    error: str = ""
    rounds: int = 0
    tool_calls: list[dict[str, object]] = field(default_factory=list)
    evidence: list[dict[str, object]] = field(default_factory=list)
    llm_calls: list[dict[str, object]] = field(default_factory=list)
    company_context: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.state == "completed"

    def to_record(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "ts_code": self.ts_code,
            "scope": "stock" if self.ts_code else "general",
            "status": "ok" if self.ok else "error",
            "state": self.state,
            "content": self.content,
            "error": self.error,
            "rounds": self.rounds,
            "tool_calls": list(self.tool_calls),
            "evidence": list(self.evidence),
            "company_context": dict(self.company_context),
        }


class TextRetrieveTool:
    """Bounded tool facade exposed to the NL Sub Agent only."""

    spec = TEXT_RETRIEVE_SPEC

    def __init__(self, retriever: TextRetriever) -> None:
        self.retriever = retriever

    def call(
        self,
        arguments: Mapping[str, object],
        *,
        default_ts_code: str,
        company_terms: list[str],
        config: NLSubAgentConfig,
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        pattern = _request_pattern(arguments)
        argument_error = _text_retrieve_argument_error(arguments, pattern)
        # A stock task is a hard evidence boundary: a model-supplied code must
        # never widen or replace the strategy's requested candidate. General
        # tasks have no default and may still opt into a stock scope.
        ts_code = str(default_ts_code or arguments.get("ts_code") or "").strip()
        raw_max = arguments.get("max_results", 5)
        max_results = (
            int(raw_max)
            if isinstance(raw_max, int) and not isinstance(raw_max, bool)
            else 5
        )
        max_results = min(max(max_results, 1), 20)
        if config.max_results_per_search is not None:
            max_results = min(max_results, config.max_results_per_search)
        search_bodies = bool(arguments.get("search_bodies", True))
        echo = {
            "pattern": pattern,
            "ts_code": ts_code,
            "max_results": max_results,
            "search_bodies": search_bodies,
        }
        if argument_error:
            return (
                {
                    "name": TEXT_RETRIEVE_TOOL,
                    "arguments": echo,
                    "status": "error",
                    "error": argument_error,
                    "hits": 0,
                    "result_ids": [],
                },
                [],
            )
        search_started = time.monotonic()
        try:
            evidence = self.retriever.search(
                pattern,
                ts_code=ts_code,
                max_results=max_results,
                search_bodies=search_bodies,
                company_terms=company_terms,
                lookback_days=config.lookback_days,
            )
        except ValueError as exc:
            # Pattern outside the RE2/grep contract: fixable tool error the
            # sub-agent can retry with a simpler pattern.
            return (
                {
                    "name": TEXT_RETRIEVE_TOOL,
                    "arguments": echo,
                    "status": "error",
                    "error": str(exc),
                    "hits": 0,
                    "result_ids": [],
                    "duration_seconds": round(time.monotonic() - search_started, 6),
                },
                [],
            )
        record = {
            "name": TEXT_RETRIEVE_TOOL,
            "arguments": echo,
            "hits": len(evidence),
            "result_ids": [item.get("text_id") for item in evidence],
            "duration_seconds": round(time.monotonic() - search_started, 6),
        }
        return record, evidence


class NLSubAgentEngine:
    """One bounded NL research task per ``ctx.nl()`` call."""

    def __init__(
        self,
        proxy: LLMProxy,
        retriever: TextRetriever | None,
        *,
        company_contexts: Mapping[str, Mapping[str, object]] | None = None,
    ) -> None:
        self.proxy = proxy
        self.retriever = retriever
        self.company_contexts = dict(company_contexts or {})
        self.text_tool = TextRetrieveTool(retriever) if retriever is not None else None

    def run(
        self,
        *,
        ts_code: str,
        prompt: str,
        request_kwargs: Mapping[str, object] | None = None,
        config: NLSubAgentConfig,
        prefetched_evidence: Sequence[Mapping[str, object]] | None = None,
        company_context: Mapping[str, object] | None = None,
        candidate_terms: Sequence[str] | None = None,
    ) -> NLSubAgentResult:
        ts_code = str(ts_code or "").strip()
        task = NLSubAgentResult(
            ts_code=ts_code, task_id=new_id("nlsub"), state="failed"
        )
        if company_context is not None:
            task.company_context = dict(company_context)
        elif ts_code:
            task.company_context = dict(
                self.company_contexts.get(
                    ts_code, {"ts_code": ts_code, "context": "unknown"}
                )
            )
        else:
            task.company_context = {"scope": "general", "context": "no_single_stock"}
        prefetched = [dict(item) for item in (prefetched_evidence or [])]
        messages = self._initial_messages(
            task,
            prompt=prompt,
            request_kwargs=dict(request_kwargs or {}),
            config=config,
            prefetched_evidence=prefetched,
        )
        terms = (
            list(candidate_terms)
            if candidate_terms is not None
            else company_terms(task.company_context, ts_code)
        )
        task.evidence.extend(prefetched)
        evidence_seen = {
            str(item.get("text_id", ""))
            for item in task.evidence
            if item.get("text_id")
        }
        rounds = config.max_tool_rounds if self.text_tool is not None else 0
        try:
            for round_index in range(1, rounds + 1):
                task.rounds = round_index
                response = self._call(
                    task, messages, config, purpose=f"subagent_round_{round_index}"
                )
                calls = _parse_native_tool_calls(response.tool_calls)
                if not calls:
                    self._finish(task, response.content, config)
                    return task
                messages.append(
                    ChatMessage(
                        "assistant",
                        response.content or None,
                        response.tool_calls,
                        reasoning_content=response.reasoning_content,
                    )
                )
                for tool_name, tool_call_id, arguments, call_error in calls:
                    new_evidence: list[dict[str, object]] = []
                    if call_error:
                        tool_record: dict[str, object] = {
                            "name": tool_name,
                            "arguments": arguments,
                            "status": "error",
                            "error": call_error,
                            "round": round_index,
                        }
                    else:
                        assert self.text_tool is not None
                        tool_record, evidence = self.text_tool.call(
                            arguments,
                            default_ts_code=ts_code,
                            company_terms=terms,
                            config=config,
                        )
                        tool_record["round"] = round_index
                        for item in evidence:
                            text_id = str(item.get("text_id", ""))
                            if text_id and text_id not in evidence_seen:
                                evidence_seen.add(text_id)
                                task.evidence.append(item)
                                new_evidence.append(
                                    _provider_evidence(
                                        item, config.max_evidence_snippet_chars
                                    )
                                )
                    task.tool_calls.append(tool_record)
                    messages.append(
                        ChatMessage(
                            "tool",
                            json.dumps(
                                {"tool_call": tool_record, "results": new_evidence},
                                ensure_ascii=False,
                                sort_keys=True,
                                default=str,
                            ),
                            tool_call_id=tool_call_id,
                        )
                    )
            task.rounds = max(task.rounds, rounds)
            final_instruction = FINAL_AFTER_TOOL_BUDGET
            if config.response_choices:
                final_instruction += (
                    " Answer with exactly one of: "
                    + ", ".join(config.response_choices)
                    + "."
                )
            messages.append(ChatMessage("user", final_instruction))
            # tool_choice="none" forces a final text answer instead of another tool call.
            response = self._call(
                task,
                messages,
                config,
                purpose="subagent_final_after_tool_budget",
                tool_choice="none",
            )
            self._finish(task, response.content, config)
        except TimeoutError as exc:
            task.state = "timeout"
            task.error = str(sanitize_for_log(str(exc)))
        except LLMProxyError as exc:
            task.state = self._failure_state(config)
            task.error = str(sanitize_for_log(str(exc)))
        except Exception as exc:  # noqa: BLE001 - convert Sub Agent failure into audited result
            task.state = self._failure_state(config)
            task.error = str(sanitize_for_log(str(exc)))
        return task

    def _call(
        self,
        task: NLSubAgentResult,
        messages: list[ChatMessage],
        config: NLSubAgentConfig,
        *,
        purpose: str,
        tool_choice: str = "auto",
    ) -> ProviderResponse:
        if (
            config.deadline_at is not None
            and config.deadline_at - time.monotonic() <= 1.0
        ):
            raise TimeoutError("NL task reached the decision wall-clock deadline")
        call_started = time.monotonic()
        detail: dict[str, object] = {
            "task_id": task.task_id,
            "ts_code": task.ts_code,
            "purpose": purpose,
            "started_at": utc_now_iso(),
            "messages": sanitize_for_log([message.to_record() for message in messages]),
            "provider": getattr(self.proxy, "provider", ""),
            "model": getattr(self.proxy, "model", ""),
        }
        tools = (
            (TEXT_RETRIEVE_SPEC.provider_record(),)
            if self.text_tool is not None
            else ()
        )
        try:
            response = self.proxy.complete(
                messages,
                tools=tools,
                tool_choice=tool_choice if tools else "none",
                max_tokens=config.max_tokens,
            )
        except Exception as exc:
            detail.update(
                status="error",
                error=sanitize_for_log(str(exc)),
                completed_at=utc_now_iso(),
                duration_seconds=round(time.monotonic() - call_started, 6),
            )
            task.llm_calls.append(detail)
            raise
        detail.update(
            status="ok",
            completed_at=utc_now_iso(),
            content=response.content,
            tool_calls=sanitize_for_log(
                [call.to_record() for call in response.tool_calls]
            ),
            usage=dict(response.usage),
            duration_seconds=round(time.monotonic() - call_started, 6),
        )
        task.llm_calls.append(detail)
        return response

    def _initial_messages(
        self,
        task: NLSubAgentResult,
        *,
        prompt: str,
        request_kwargs: dict[str, object],
        config: NLSubAgentConfig,
        prefetched_evidence: list[dict[str, object]],
    ) -> list[ChatMessage]:
        as_of = (
            getattr(self.retriever, "as_of", None)
            if self.retriever is not None
            else None
        )
        body: dict[str, object] = {
            "request": {
                "ts_code": task.ts_code,
                "prompt": prompt,
                "kwargs": request_kwargs,
            },
            "company_context": task.company_context,
            "decision_as_of": str(as_of) if as_of is not None else "",
        }
        if config.response_choices:
            body["response_contract"] = {
                "type": "enum",
                "values": list(config.response_choices),
                "instruction": "Return exactly one listed value and no explanation.",
            }
        if prefetched_evidence:
            body["prefetched_evidence"] = [
                _provider_evidence(item, config.max_evidence_snippet_chars)
                for item in prefetched_evidence
            ]
        return [
            ChatMessage("system", SUB_AGENT_SYSTEM_PROMPT),
            ChatMessage(
                "user",
                json.dumps(body, ensure_ascii=False, sort_keys=True, default=str),
            ),
        ]

    def _finish(
        self, task: NLSubAgentResult, content: str, config: NLSubAgentConfig
    ) -> None:
        if not config.response_choices:
            task.content = content
            task.state = "completed"
            return
        choice = _first_enum_value(content, config.response_choices)
        if choice is None:
            task.state = self._failure_state(config)
            task.error = "structured NL response did not contain a permitted enum value"
            return
        task.content = choice
        task.state = "completed"

    @staticmethod
    def _failure_state(config: NLSubAgentConfig) -> str:
        return (
            "failed_with_policy"
            if config.failure_policy == "return_error_with_audit"
            else "failed"
        )


def _parse_native_tool_calls(
    tool_calls: Sequence[ToolCall],
) -> list[tuple[str, str, dict[str, object], str]]:
    """Pull native ``text_retrieve`` calls and keep malformed arguments auditable."""
    parsed: list[tuple[str, str, dict[str, object], str]] = []
    for tool_call in tool_calls or ():
        tool_call_id = str(getattr(tool_call, "id", "") or new_id("call"))
        tool_name = str(getattr(tool_call, "name", "") or "")
        if tool_name != TEXT_RETRIEVE_TOOL:
            parsed.append(
                (
                    tool_name or "unknown",
                    tool_call_id,
                    {},
                    f"unsupported NL tool call: {tool_name or 'unknown'}; available tool is {TEXT_RETRIEVE_TOOL}",
                )
            )
            continue
        parsed.append((TEXT_RETRIEVE_TOOL, tool_call_id, dict(tool_call.arguments), ""))
    return parsed


def _request_pattern(request: object) -> str:
    """Pattern from a search request (the schema's only query field)."""
    if not isinstance(request, Mapping):
        return ""
    return str(request.get("pattern", "") or "").strip()


def _text_retrieve_argument_error(arguments: Mapping[str, object], pattern: str) -> str:
    raw_pattern = arguments.get("pattern")
    if raw_pattern is not None and not isinstance(raw_pattern, str):
        return "text_retrieve pattern must be a string"
    if not pattern:
        return "text_retrieve requires a non-empty pattern"
    unknown = sorted(
        set(arguments) - {"pattern", "ts_code", "max_results", "search_bodies"}
    )
    if unknown:
        return f"unknown text_retrieve arguments: {unknown}"
    return ""


def _provider_evidence(
    item: Mapping[str, object], snippet_chars: int | None
) -> dict[str, object]:
    projected = dict(item)
    if snippet_chars is not None:
        projected["snippet"] = str(projected.get("snippet") or "")[:snippet_chars]
    return projected


def _enum_token_pattern(choice: str) -> str:
    """Standalone-token pattern for one enum value.

    ASCII values keep the ASCII word guard so ``结论PASS`` still parses. CJK has
    no delimiters, so a CJK-bearing value adjacent to any word char (``不减持``,
    ``减持压力``) is ambiguous — refusing to parse it surfaces an auditable
    failure instead of a silently inverted label. ``\\w`` covers CJK in Python.
    """
    boundary = r"\w" if re.search(r"[^\x00-\x7f]", choice) else r"[A-Za-z0-9_]"
    return rf"(?<!{boundary}){re.escape(choice)}(?!{boundary})"


def _first_enum_value(content: str, choices: tuple[str, ...]) -> str | None:
    """Return the first standalone allowed token; raw content remains in the provider audit."""
    if not choices:
        return None
    by_folded = {choice.casefold(): choice for choice in choices}
    alternatives = "|".join(
        _enum_token_pattern(choice) for choice in sorted(choices, key=len, reverse=True)
    )
    match = re.search(
        rf"(?:{alternatives})",
        str(content or ""),
        flags=re.IGNORECASE,
    )
    return by_folded.get(match.group(0).casefold()) if match is not None else None


def company_terms(context: Mapping[str, object], ts_code: str) -> list[str]:
    code = str(ts_code or "").strip()
    terms: list[str] = [code] if code else []
    for key in ("name", "fullname", "company_name", "short_name"):
        value = context.get(key)
        if isinstance(value, str) and value.strip():
            terms.append(value.strip())
    return terms


__all__ = [
    "ENUM_MAX_RESULTS",
    "ENUM_MAX_TOKENS",
    "ENUM_SNIPPET_CHARS",
    "MAX_TOOL_ROUNDS",
    "TEXT_RETRIEVE_SPEC",
    "TEXT_RETRIEVE_TOOL",
    "NLSubAgentConfig",
    "NLSubAgentEngine",
    "NLSubAgentResult",
    "TextRetrieveTool",
    "company_terms",
]
