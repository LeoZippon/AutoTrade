"""Strategy scheduling, point-in-time context, and JSON order contract.

This module is the single source of truth shared by strategy authors, replay,
and scheduled execution.  Strategies receive an immutable context and return plain
JSON-compatible order objects; they never receive a Broker or an environment
tool surface.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time
from itertools import pairwise
from types import MappingProxyType
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

CN_TZ = ZoneInfo("Asia/Shanghai")
StrategyPeriod = Literal["day", "month", "quarter", "year"]
OrderAction = Literal["buy", "sell"]
_PERIODS = frozenset({"day", "month", "quarter", "year"})


class StrategyContractError(ValueError):
    """The schedule, context, or an Agent-produced order is invalid."""


class _ValidatedStrategyBar(Mapping[str, object]):
    """Immutable strict-JSON bar already checked at its trust boundary."""

    __slots__ = ("_available_at", "_identity", "_record")

    def __init__(
        self,
        record: dict[str, object],
        available_at: datetime,
        identity: tuple[object, ...],
    ) -> None:
        self._record = MappingProxyType(record)
        self._available_at = available_at
        self._identity = identity

    def __getitem__(self, key: str) -> object:
        return self._record[key]

    def __iter__(self):
        return iter(self._record)

    def __len__(self) -> int:
        return len(self._record)

    def __repr__(self) -> str:
        return repr(self._record)


class _ValidatedStrategyBars(tuple[Mapping[str, object], ...]):
    """Tuple marker that avoids revalidating an already checked bar prefix."""

    _max_available_at: datetime | None
    _available_at_monotonic: bool

    def __new__(
        cls,
        values=(),
        *,
        max_available_at: datetime | None = None,
        available_at_monotonic: bool = False,
    ):
        instance = super().__new__(cls, values)
        instance._max_available_at = max_available_at
        instance._available_at_monotonic = available_at_monotonic
        return instance

    def __getitem__(self, key):
        value = super().__getitem__(key)
        if not isinstance(key, slice):
            return value
        monotonic = self._available_at_monotonic and (key.step is None or key.step > 0)
        if not value:
            maximum = None
        elif monotonic:
            maximum = value[-1]._available_at
        else:
            maximum = max(item._available_at for item in value)
        return type(self)(
            value,
            max_available_at=maximum,
            available_at_monotonic=monotonic,
        )


def _parse_time(value: str | time) -> time:
    if isinstance(value, time):
        if value.tzinfo is not None:
            raise StrategyContractError("inference_time must be a local HH:MM without a timezone")
        return value.replace(second=0, microsecond=0)
    text = str(value)
    try:
        parsed = time.fromisoformat(text)
    except ValueError as exc:
        raise StrategyContractError("inference_time must use 24-hour HH:MM") from exc
    if len(text) != 5 or text[2] != ":" or parsed.second or parsed.microsecond:
        raise StrategyContractError("inference_time must use 24-hour HH:MM")
    return parsed


def _as_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value)
    normalized = f"{text[:4]}-{text[4:6]}-{text[6:8]}" if len(text) == 8 and text.isdigit() else text
    try:
        return date.fromisoformat(normalized)
    except ValueError as exc:
        raise StrategyContractError(f"invalid trade date: {value!r}") from exc


@dataclass(frozen=True)
class StrategySchedule:
    """User-selected inference cadence and local China-market time."""

    period: StrategyPeriod = "day"
    inference_time: str | time = "08:30"

    def __post_init__(self) -> None:
        if self.period not in _PERIODS:
            raise StrategyContractError(f"period must be one of {sorted(_PERIODS)}")
        parsed = _parse_time(self.inference_time)
        object.__setattr__(self, "inference_time", parsed.strftime("%H:%M"))

    def at(self, trade_date: str | date | datetime) -> datetime:
        return datetime.combine(_as_date(trade_date), _parse_time(self.inference_time), tzinfo=CN_TZ)

    def is_due(
        self,
        trade_date: str | date | datetime,
        previous_trade_date: str | date | datetime | None,
    ) -> bool:
        """Run on each day or the first available trading day of a new period."""

        current = _as_date(trade_date)
        if self.period == "day" or previous_trade_date is None:
            return True
        previous = _as_date(previous_trade_date)
        if self.period == "month":
            return (current.year, current.month) != (previous.year, previous.month)
        if self.period == "quarter":
            return (current.year, (current.month - 1) // 3) != (
                previous.year,
                (previous.month - 1) // 3,
            )
        return current.year != previous.year

    def to_record(self) -> dict[str, str]:
        return {"period": self.period, "inference_time": str(self.inference_time)}


@dataclass(frozen=True)
class StrategyOrder:
    symbol: str
    action: OrderAction
    quantity: int
    execute_at: datetime
    metadata: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def from_record(cls, value: object, *, inference_at: datetime) -> StrategyOrder:
        if not isinstance(value, Mapping):
            raise StrategyContractError("each order must be a JSON object")
        required = {"symbol", "action", "quantity", "execute_at"}
        missing = sorted(required.difference(value))
        if missing:
            raise StrategyContractError(f"order missing required fields: {missing}")
        symbol = str(value["symbol"]).strip()
        if not symbol:
            raise StrategyContractError("order symbol must be non-empty")
        action = value["action"]
        if action not in ("buy", "sell"):
            raise StrategyContractError("order action must be buy or sell")
        quantity = value["quantity"]
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise StrategyContractError("order quantity must be a positive integer")
        execute_at = _parse_datetime(value["execute_at"])
        normalized_inference = _require_cn_datetime(inference_at, "inference_at")
        if execute_at < normalized_inference:
            raise StrategyContractError("order execute_at cannot be earlier than the PIT inference time")
        metadata = {str(key): item for key, item in value.items() if key not in required}
        return cls(
            symbol=symbol,
            action=action,
            quantity=quantity,
            execute_at=execute_at,
            metadata=MappingProxyType(metadata),
        )

    def to_record(self) -> dict[str, object]:
        return {
            **self.metadata,
            "symbol": self.symbol,
            "action": self.action,
            "quantity": self.quantity,
            "execute_at": self.execute_at.isoformat(),
        }


def _parse_datetime(value: object, name: str = "order execute_at") -> datetime:
    if not isinstance(value, str):
        raise StrategyContractError(f"{name} must be an ISO-8601 string with timezone")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise StrategyContractError(f"{name} must be an ISO-8601 string with timezone") from exc
    return _require_cn_datetime(parsed, name)


def _require_cn_datetime(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise StrategyContractError(f"{name} must include a timezone")
    normalized = value.astimezone(CN_TZ)
    if normalized.utcoffset() != CN_TZ.utcoffset(normalized):
        raise StrategyContractError(f"{name} must identify a valid point in time")
    return normalized


def validate_order_payload(payload: object, *, inference_at: datetime) -> tuple[StrategyOrder, ...]:
    """Round-trip and validate the complete Agent-to-environment JSON payload."""

    try:
        normalized = json.loads(json.dumps(payload, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise StrategyContractError("strategy output must be JSON-compatible") from exc
    if not isinstance(normalized, list):
        raise StrategyContractError("strategy output must be a JSON array of orders")
    return tuple(StrategyOrder.from_record(item, inference_at=inference_at) for item in normalized)


@dataclass(frozen=True)
class AccountSnapshot:
    cash: float
    positions: Mapping[str, int]

    def __post_init__(self) -> None:
        if isinstance(self.cash, bool) or not isinstance(self.cash, (int, float)):
            raise StrategyContractError("account cash must be a non-negative finite number")
        if not math.isfinite(self.cash) or self.cash < 0:
            raise StrategyContractError("account cash must be a non-negative finite number")
        positions: dict[str, int] = {}
        for symbol, quantity in self.positions.items():
            if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 0:
                raise StrategyContractError("position quantities must be non-negative integers")
            normalized_symbol = str(symbol).strip()
            if not normalized_symbol:
                raise StrategyContractError("position symbols must be non-empty strings")
            positions[normalized_symbol] = quantity
        object.__setattr__(self, "cash", float(self.cash))
        object.__setattr__(self, "positions", MappingProxyType(positions))

    def to_record(self) -> dict[str, object]:
        return {"cash": self.cash, "positions": dict(self.positions)}

    @classmethod
    def from_record(cls, value: object) -> AccountSnapshot:
        record = _strict_record(value, required={"cash", "positions"}, name="account")
        positions = record["positions"]
        if not isinstance(positions, Mapping):
            raise StrategyContractError("account positions must be a JSON object")
        return cls(cash=record["cash"], positions=positions)  # type: ignore[arg-type]


class NLQuery(Protocol):
    def __call__(
        self,
        request: Mapping[str, object],
        *,
        inference_at: datetime,
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True)
class StrategyContext:
    """Immutable PIT input with one narrow host-mediated NL capability."""

    inference_at: datetime
    bars: tuple[Mapping[str, object], ...]
    account: AccountSnapshot
    snapshot_dir: str = ""
    asof_dir: str = ""
    asof_version: str = "0"
    _nl_query: NLQuery | None = field(default=None, repr=False, compare=False)
    _bar_available_at: tuple[datetime, ...] = field(
        default=(), init=False, repr=False, compare=False
    )
    _bar_identity: tuple[tuple[object, ...], ...] = field(
        default=(), init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        inference_at = _require_cn_datetime(self.inference_at, "inference_at")
        if isinstance(self.bars, _ValidatedStrategyBars):
            normalized = self.bars
            if (
                normalized._max_available_at is not None
                and normalized._max_available_at > inference_at
            ):
                raise StrategyContractError("strategy context contains data not visible at inference time")
        else:
            normalized = [
                _validated_strategy_bar(raw, inference_at=inference_at) for raw in self.bars
            ]
            maximum = max((bar._available_at for bar in normalized), default=None)
            monotonic = all(
                left._available_at <= right._available_at
                for left, right in pairwise(normalized)
            )
            normalized = _ValidatedStrategyBars(
                normalized,
                max_available_at=maximum,
                available_at_monotonic=monotonic,
            )
        object.__setattr__(self, "inference_at", inference_at)
        object.__setattr__(self, "bars", tuple(bar._record for bar in normalized))
        object.__setattr__(
            self,
            "_bar_available_at",
            tuple(bar._available_at for bar in normalized),
        )
        object.__setattr__(self, "_bar_identity", tuple(bar._identity for bar in normalized))
        for name in ("snapshot_dir", "asof_dir", "asof_version"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise StrategyContractError(f"{name} must be a string")
            if "\x00" in value:
                raise StrategyContractError(f"{name} cannot contain NUL")

    def history(self, symbol: str) -> tuple[Mapping[str, object], ...]:
        return tuple(row for row in self.bars if str(row.get("symbol")) == str(symbol))

    def latest(self, symbol: str) -> Mapping[str, object] | None:
        rows = self.history(symbol)
        return rows[-1] if rows else None

    def nl(self, **request: object) -> Mapping[str, object]:
        """Make one JSON-only NL request through the trusted host service."""

        if self._nl_query is None:
            raise StrategyContractError("NL service is not configured for this strategy context")
        normalized = _json_mapping(request, name="NL request")
        _validate_pit_tree(normalized, inference_at=self.inference_at, name="NL request")
        response = self._nl_query(normalized, inference_at=self.inference_at)
        normalized_response = _json_mapping(response, name="NL response")
        _validate_pit_tree(normalized_response, inference_at=self.inference_at, name="NL response")
        return MappingProxyType(normalized_response)

    def to_record(self) -> dict[str, object]:
        record = {
            "inference_at": self.inference_at.isoformat(),
            "bars": [dict(row) for row in self.bars],
            "account": self.account.to_record(),
            "snapshot_dir": self.snapshot_dir,
            "asof_dir": self.asof_dir,
            "asof_version": self.asof_version,
        }
        return _json_mapping(record, name="strategy context")

    @classmethod
    def from_record(
        cls,
        value: object,
        *,
        nl_query: NLQuery | None = None,
    ) -> StrategyContext:
        record = _strict_record(
            value,
            required={
                "inference_at",
                "bars",
                "account",
                "snapshot_dir",
                "asof_dir",
                "asof_version",
            },
            name="strategy context",
        )
        bars = record["bars"]
        if not isinstance(bars, list):
            raise StrategyContractError("strategy context bars must be a JSON array")
        return cls(
            inference_at=_parse_datetime(record["inference_at"], "inference_at"),
            bars=tuple(bars),  # type: ignore[arg-type]
            account=AccountSnapshot.from_record(record["account"]),
            snapshot_dir=record["snapshot_dir"],  # type: ignore[arg-type]
            asof_dir=record["asof_dir"],  # type: ignore[arg-type]
            asof_version=record["asof_version"],  # type: ignore[arg-type]
            _nl_query=nl_query,
        )


def _strict_record(value: object, *, required: set[str], name: str) -> dict[str, object]:
    record = _json_mapping(value, name=name)
    keys = set(record)
    missing = sorted(required - keys)
    extra = sorted(keys - required)
    if missing:
        raise StrategyContractError(f"{name} missing required fields: {missing}")
    if extra:
        raise StrategyContractError(f"{name} contains unsupported fields: {extra}")
    return record


def _json_mapping(value: object, *, name: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise StrategyContractError(f"{name} must be a JSON object")
    try:
        normalized = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise StrategyContractError(f"{name} must be JSON-compatible") from exc
    if not isinstance(normalized, dict):
        raise StrategyContractError(f"{name} must be a JSON object")
    return normalized


def _validated_strategy_bar(
    value: object,
    *,
    inference_at: datetime | None = None,
    decoded_json: bool = False,
) -> _ValidatedStrategyBar:
    """Normalize a host bar once, or validate one freshly decoded from JSON."""

    if decoded_json:
        if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
            raise StrategyContractError("strategy bar must be a JSON object")
        record = value
    else:
        if not isinstance(value, Mapping):
            raise StrategyContractError("each strategy bar must be a JSON object")
        record = _json_mapping(value, name="strategy bar")
    available = _parse_datetime(record.get("available_at"), "bar available_at")
    if inference_at is not None and available > inference_at:
        raise StrategyContractError("strategy context contains data not visible at inference time")
    return _ValidatedStrategyBar(record, available, _strict_json_identity(record))


def _strict_json_identity(value: object) -> tuple[object, ...]:
    """Hashable JSON tree identity that preserves bool/int/float distinctions."""

    if value is None:
        return ("null",)
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, int):
        return ("int", value)
    if isinstance(value, float):
        return ("float", value.hex())
    if isinstance(value, str):
        return ("str", value)
    if isinstance(value, list):
        return ("list", tuple(_strict_json_identity(item) for item in value))
    if isinstance(value, dict):
        return (
            "object",
            tuple((key, _strict_json_identity(item)) for key, item in sorted(value.items())),
        )
    raise StrategyContractError("strategy bar must contain only strict JSON values")


def _validate_pit_tree(value: object, *, inference_at: datetime, name: str) -> None:
    """Reject explicit availability timestamps later than the current PIT cut."""

    if isinstance(value, Mapping):
        available_at = value.get("available_at")
        if (
            available_at is not None
            and _parse_datetime(available_at, f"{name} available_at") > inference_at
        ):
            raise StrategyContractError(f"{name} contains data not visible at inference time")
        for child in value.values():
            _validate_pit_tree(child, inference_at=inference_at, name=name)
    elif isinstance(value, list):
        for child in value:
            _validate_pit_tree(child, inference_at=inference_at, name=name)


StrategyFunction = Callable[[StrategyContext], Sequence[Mapping[str, object]]]


def run_strategy(strategy: StrategyFunction, context: StrategyContext) -> tuple[StrategyOrder, ...]:
    return validate_order_payload(strategy(context), inference_at=context.inference_at)
