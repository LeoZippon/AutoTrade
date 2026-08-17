"""The Meta Taste must not carry calendar knowledge forward.

The Taste is injected into every later Fold prompt, so a date in it is
hidden-schedule evidence crossing the boundary — the same anti-leakage class as
the fold-ref invariant, and the one a blanket test exclusion concealed.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from autotrade.agent.runner import (
    TASTE_MAX_CHARS,
    TasteFinishTool,
    taste_policy_violation,
    visible_window_dates,
)
from autotrade.environment.tools import SafeWorkspace, ToolError, ToolRegistry

MANIFEST_2021 = {
    "meta_learning_visible_fold": {
        "input_window": "20200101..20210930",
        "validation_period": "20211001..20211231",
        "valid_decision_time": "2021-10-08T09:25:00+08:00",
    },
    "valid_decision_time": "2021-10-08T09:25:00+08:00",
}
MANIFEST_2024 = {
    "meta_learning_visible_fold": {
        "input_window": "20240101..20240930",
        "validation_period": "20241001..20241231",
        "valid_decision_time": "2024-10-08T09:25:00+08:00",
    },
    "valid_decision_time": "2024-10-08T09:25:00+08:00",
}


def _taste(root: Path, text: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "taste.md"
    path.write_text(text, encoding="utf-8")
    return path


class TastePolicyTest(unittest.TestCase):
    def test_the_window_is_derived_from_the_manifest_not_hard_coded(self) -> None:
        dates = visible_window_dates(MANIFEST_2021)
        self.assertEqual(
            dates, {"2020", "2021", "20200101", "20210930", "20211001", "20211231"}
        )
        self.assertEqual(visible_window_dates(MANIFEST_2024) & {"2021"}, set())
        self.assertIn("2024", visible_window_dates(MANIFEST_2024))
        # A manifest with no visible fold yields no window terms.
        self.assertEqual(visible_window_dates({}), set())

    def test_a_calendar_date_blocks_the_taste(self) -> None:
        with TemporaryDirectory() as tmp:
            path = _taste(
                Path(tmp),
                "# 品味\n## 一\n日内数据仅覆盖 21 个交易日（2021 年 8-9 月），样本不足。",
            )
            violation = taste_policy_violation(path, window_dates=visible_window_dates(MANIFEST_2021))
            self.assertTrue(violation)
            self.assertTrue(violation.startswith("taste.md line "))
            self.assertIn("calendar date", violation)

    def test_a_bare_visible_window_year_is_caught_and_tracks_the_window(self) -> None:
        with TemporaryDirectory() as tmp:
            path = _taste(Path(tmp), "# 品味\n## 一\n对标 2024 的市场结构轮动。")
            # The 2024 window forbids a bare 2024 …
            self.assertIn(
                "calendar date",
                taste_policy_violation(path, window_dates=visible_window_dates(MANIFEST_2024)),
            )
            # … and the very same text is acceptable under the 2021 window, which
            # is the point: the rule follows the window, not a fixed year.
            self.assertEqual(
                taste_policy_violation(path, window_dates=visible_window_dates(MANIFEST_2021)), ""
            )

    def test_a_non_window_year_reading_as_a_regime_reference_is_allowed(self) -> None:
        with TemporaryDirectory() as tmp:
            path = _taste(
                Path(tmp), "# 品味\n## 一\n借鉴 2008 式系统性风险的应对，按季度控制回撤。"
            )
            self.assertEqual(
                taste_policy_violation(path, window_dates=visible_window_dates(MANIFEST_2024)), ""
            )

    def test_cadence_words_counts_and_percentages_are_transferable(self) -> None:
        with TemporaryDirectory() as tmp:
            path = _taste(
                Path(tmp),
                "# 品味\n## 一\n核心持仓按季度轮动；日内样本交易日不足（约 21 个），换手率 50%-80%。",
            )
            self.assertEqual(
                taste_policy_violation(path, window_dates=visible_window_dates(MANIFEST_2021)), ""
            )

    def test_a_ledger_length_taste_is_refused(self) -> None:
        with TemporaryDirectory() as tmp:
            path = _taste(Path(tmp), "# 品味\n" + ("可迁移方向。\n" * (TASTE_MAX_CHARS // 6)))
            violation = taste_policy_violation(path, window_dates=set())
            self.assertIn("characters", violation)
            self.assertIn(str(TASTE_MAX_CHARS), violation)

    def test_a_missing_or_empty_taste_is_refused(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertIn("write taste.md", taste_policy_violation(root / "taste.md", window_dates=set()))
            self.assertIn(
                "non-empty", taste_policy_violation(_taste(root, "   \n"), window_dates=set())
            )


class TasteFinishToolTest(unittest.TestCase):
    """The guard is wired into the terminal tool, so a dated Taste yields a
    typed, fixable observation instead of an accepted session."""

    def _registry(self, root: Path, manifest: dict) -> ToolRegistry:
        return ToolRegistry(
            [TasteFinishTool(SafeWorkspace(root), window_dates=visible_window_dates(manifest))]
        )

    def test_finish_meta_refuses_a_dated_taste_with_a_typed_error(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _taste(root, "# 品味\n2021 年四季度动量最好。")
            result = self._registry(root, MANIFEST_2021).invoke(
                "finish_meta", {"taste_path": "taste.md"}
            )
            self.assertFalse(result.ok)
            self.assertEqual(result.value["error_type"], "taste_policy")
            self.assertIn("calendar date", result.error)

    def test_finish_meta_accepts_a_transferable_taste_and_reports_done(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _taste(root, "# 品味\n样本交易日不足时降低换手；按季度轮动，持仓不超过 2000 只股票。")
            result = self._registry(root, MANIFEST_2021).invoke(
                "finish_meta", {"taste_path": "taste.md"}
            )
            self.assertTrue(result.ok, result.error)
            self.assertEqual(result.value["taste_path"], "taste.md")
            # Pipeline adopts a Taste only on an explicit done.
            self.assertEqual(result.value["status"], "meta_learning_done")

    def test_the_agent_can_rewrite_and_finish_after_a_refusal(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = self._registry(root, MANIFEST_2021)
            _taste(root, "# 品味\n在 20211001 之后减仓。")
            self.assertFalse(registry.invoke("finish_meta", {"taste_path": "taste.md"}).ok)
            _taste(root, "# 品味\n估值分位偏高时减仓，与具体日期无关。")
            self.assertTrue(registry.invoke("finish_meta", {"taste_path": "taste.md"}).ok)

    def test_the_tool_refuses_a_path_outside_the_workspace(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "workspace"
            root.mkdir()
            outside = Path(tmp) / "taste.md"
            outside.write_text("# 品味\n可迁移。", encoding="utf-8")
            with self.assertRaises(ToolError):
                TasteFinishTool(SafeWorkspace(root)).invoke({"taste_path": "../taste.md"})


if __name__ == "__main__":
    unittest.main()
