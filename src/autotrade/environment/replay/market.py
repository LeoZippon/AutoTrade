"""Normalized daily market data with point-in-time visibility."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Mapping
from datetime import date, datetime, time

import pandas as pd

from autotrade.environment.strategy import (
    CN_TZ,
    StrategyContractError,
    _validated_strategy_bar,
    _ValidatedStrategyBars,
)


class DailyMarketData:
    REQUIRED = ("trade_date", "open", "close")

    def __init__(self, daily: pd.DataFrame) -> None:
        frame = daily.copy()
        if "symbol" not in frame.columns and "ts_code" in frame.columns:
            frame = frame.rename(columns={"ts_code": "symbol"})
        missing = [column for column in (*self.REQUIRED, "symbol") if column not in frame.columns]
        if missing:
            raise ValueError(f"daily market data missing columns: {missing}")
        frame["trade_date"] = frame["trade_date"].map(_date_text)
        frame["symbol"] = frame["symbol"].astype(str).str.strip()
        if (frame["symbol"] == "").any():
            raise ValueError("daily market data contains an empty symbol")
        duplicates = frame.duplicated(["trade_date", "symbol"], keep=False)
        if duplicates.any():
            keys = frame.loc[duplicates, ["trade_date", "symbol"]].drop_duplicates().head(5).to_dict("records")
            raise ValueError(f"daily market data has duplicate business keys: {keys}")
        if "available_at" not in frame.columns:
            frame["available_at"] = frame["trade_date"].map(_default_available_at)
        else:
            frame["available_at"] = frame["available_at"].map(_available_at)
        frame = frame.sort_values(["available_at", "trade_date", "symbol"]).reset_index(drop=True)
        self.trade_dates = tuple(sorted(frame["trade_date"].unique()))
        self._by_day: dict[str, dict[str, Mapping[str, object]]] = {}
        normalized = [
            _validated_strategy_bar(_record(row)) for row in frame.to_dict(orient="records")
        ]
        records = _ValidatedStrategyBars(
            normalized,
            max_available_at=normalized[-1]._available_at if normalized else None,
            available_at_monotonic=True,
        )
        self._records = records
        self._available_at = tuple(row._available_at for row in records)
        for row in records:
            trade_date = str(row["trade_date"])
            self._by_day.setdefault(trade_date, {})[str(row["symbol"])] = row

    def bars_for_day(self, trade_date: str) -> Mapping[str, Mapping[str, object]]:
        return self._by_day.get(str(trade_date), {})

    def visible_at(self, inference_at: datetime) -> tuple[Mapping[str, object], ...]:
        if inference_at.tzinfo is None or inference_at.utcoffset() is None:
            raise StrategyContractError("inference_at must include a timezone")
        cutoff = inference_at.astimezone(CN_TZ)
        return self._records[:bisect_right(self._available_at, cutoff)]


def _date_text(value: object) -> str:
    text = str(value)
    normalized = f"{text[:4]}-{text[4:6]}-{text[6:8]}" if len(text) == 8 and text.isdigit() else text
    try:
        return date.fromisoformat(normalized).strftime("%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"invalid trade_date: {value!r}") from exc


def _default_available_at(trade_date: str) -> datetime:
    day = date.fromisoformat(f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}")
    return datetime.combine(day, time(17, 30), tzinfo=CN_TZ)


def _available_at(value: object) -> datetime:
    if isinstance(value, pd.Timestamp):
        parsed = value.to_pydatetime()
    elif isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError as exc:
            raise ValueError(f"invalid available_at: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("available_at must include a timezone")
    return parsed.astimezone(CN_TZ)


def _record(value: dict[str, object]) -> dict[str, object]:
    record: dict[str, object] = {}
    for key, item in value.items():
        if isinstance(item, pd.Timestamp):
            item = item.to_pydatetime()
        if isinstance(item, datetime):
            record[str(key)] = item.astimezone(CN_TZ).isoformat()
        elif hasattr(item, "item"):
            record[str(key)] = _missing_to_none(item.item())
        else:
            record[str(key)] = _missing_to_none(item)
    return record


def _missing_to_none(value: object) -> object:
    """Normalize scalar pandas missing values into strict JSON nulls."""

    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return value
    try:
        return None if bool(missing) else value
    except (TypeError, ValueError):
        return value


__all__ = ["DailyMarketData"]
