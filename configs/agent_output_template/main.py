"""Formal daily strategy entrypoint -- minimal working baseline.

The Environment calls ``generate_orders(context)`` only at the configured
day/month/quarter/year schedule and fixed Asia/Shanghai time. This example is
intentionally small: while flat, it builds an equal-budget basket from symbols
with a visible positive close and submits buys at the next same-day daily price
timestamp. An after-close invocation emits no order because the strategy does
not receive a future trading calendar.
Replace the placeholder symbol ordering and add an explicit exit lifecycle.
"""

from __future__ import annotations

import math

TOP_N = 10
CASH_FRACTION = 0.95


def _same_day_execution(inference_at):
    market_open = inference_at.replace(hour=9, minute=30, second=0, microsecond=0)
    if inference_at <= market_open:
        return market_open
    market_close = inference_at.replace(hour=15, minute=0, second=0, microsecond=0)
    if inference_at <= market_close:
        return market_close
    return None


def _visible_prices(context):
    """Return the last visible positive close for each normalized symbol."""

    prices = {}
    for row in context.bars:
        symbol = str(row.get("symbol") or "").strip()
        value = row.get("close")
        if (
            symbol
            and not isinstance(value, bool)
            and isinstance(value, (int, float))
            and math.isfinite(float(value))
            and float(value) > 0
        ):
            prices[symbol] = float(value)
    return prices


def generate_orders(context):
    if context.account.positions:
        return []

    prices = _visible_prices(context)
    symbols = sorted(prices)[:TOP_N]
    if not symbols:
        return []

    execution_at = _same_day_execution(context.inference_at)
    if execution_at is None:
        return []
    execution = execution_at.isoformat()
    remaining = float(context.account.cash) * CASH_FRACTION
    orders = []
    for index, symbol in enumerate(symbols):
        price = prices[symbol]
        target_budget = remaining / (len(symbols) - index)
        quantity = int(target_budget / price // 100 * 100)
        if quantity <= 0:
            continue
        orders.append(
            {
                "symbol": symbol,
                "action": "buy",
                "quantity": quantity,
                "execute_at": execution,
                "reason": "visible_equal_budget_baseline",
            }
        )
        remaining -= quantity * price
    return orders
