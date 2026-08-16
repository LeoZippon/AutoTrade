"""Direct daily backtest entrypoint for an Agent-authored strategy."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd

from autotrade.environment.broker import BrokerProfile
from autotrade.environment.executor import StrategyExecutor
from autotrade.environment.replay import ReplayResult
from autotrade.environment.sandbox import SandboxConfig
from autotrade.environment.strategy import StrategySchedule
from autotrade.environment.strategy_loader import validate_strategy_source
from autotrade.pipelines import DailyStrategyPipeline, StrategyExperimentConfig


class BacktestTool:
    """Small wrapper used by local callers; it keeps the result in memory."""

    def __init__(
        self,
        *,
        strategy_path: str | Path,
        schedule: StrategySchedule,
        broker_profile: BrokerProfile | None = None,
        execution_mode: str = "sandbox",
        sandbox: SandboxConfig | None = None,
        nl_query=None,
        executor_factory: Callable[[StrategyExperimentConfig], StrategyExecutor] | None = None,
    ) -> None:
        self.strategy_path = Path(strategy_path)
        self.schedule = schedule
        self.broker_profile = broker_profile or BrokerProfile()
        self.execution_mode = execution_mode
        self.sandbox = sandbox or SandboxConfig()
        self.nl_query = nl_query
        self.executor_factory = executor_factory

    def contract_check(self) -> dict[str, object]:
        validate_strategy_source(
            self.strategy_path.read_text(encoding="utf-8"),
            filename=self.strategy_path.name,
        )
        return {
            "status": "ok",
            "strategy_entry": "generate_orders",
            "schedule": self.schedule.to_record(),
            "execution_mode": self.execution_mode,
        }

    def run(self, daily: pd.DataFrame | str | Path) -> ReplayResult:
        frame = pd.read_parquet(daily) if isinstance(daily, (str, Path)) else daily
        if not isinstance(frame, pd.DataFrame):
            raise TypeError("daily must be a pandas DataFrame or parquet path")
        config = StrategyExperimentConfig(
            strategy_path=self.strategy_path,
            schedule=self.schedule,
            broker_profile=self.broker_profile,
            execution_mode=self.execution_mode,  # type: ignore[arg-type]
            sandbox=self.sandbox,
        )
        return DailyStrategyPipeline(
            config,
            nl_query=self.nl_query,
            executor_factory=self.executor_factory,
        ).run(frame)


__all__ = ["BacktestTool"]
