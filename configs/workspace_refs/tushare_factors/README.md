# TuShare 因子参考（只读）

这些文件只是参考，正式策略必须写到 `/mnt/agent/workspace/output/main.py`。
禁止把整棵参考树拷进 `output`；禁止在正式策略里写死 `/mnt/agent/workspace`。
正式回放只能 `numpy`/`pandas` + 单文件；用 PIT：`available_at <= inference_at`；默认 `08:30` 只能用 T-1 日线。
财务用公告日/`available_at`，不用 `end_date` 偷看。

## 任务

用 PIT parquet **自己重算**这些因子，组合或优化后写成 `generate_orders(context)`。
本目录只提供公式与符号约定，不提供供应商 `factor_value`，也不挂载付费因子库接口。

TuShare 付费因子库（`factor_list`，doc_id=486）现有 **202** 个股票因子、**9** 个家族。
本环境没有下载该库的日度取值。`stk_factor` / `stk_factor_pro` 技术指标可用日线重算，但它们按**最新交易日往前复权**的快照口径生产，**同一交易日盘前不可用**，且与本环境「T-1 冻结复权」不一致。

优先实现 `compute_set.md` 的 40 个 PIT 安全因子；`family_index.md` 给出 202 个名字与一行公式，便于扩展，不要一次全算。

## 本包文件

| 文件 | 用途 |
|---|---|
| `pit_rules.md` | 日线、复权、财务、截面排名的可见时间 |
| `compute_set.md` | 40 个建议重算因子：公式、符号、翻转 |
| `family_index.md` | 202 个官方因子按家族索引 |

## 输入从哪读

长窗口日线从 `context.asof_dir + "/daily"` 读已确认列，并截到有限尾窗。
财务从 `fundamentals` 域读，只保留 `available_at <= inference_at` 的已公告记录。
指数对照（沪深300、上证）从 `macro` 的 `index_daily` 读，单位按本次 `data_summary.json` 核对。
换手、市值、估值优先用归一化日线里已有的 `turnover_rate`、`circ_mv`、`total_mv`、`pe_ttm` 等，不要猜单位。

## 不要做的事

- 不要调用或假设存在 `factor_value` / `stk_factor` 当日行。
- 不要把供应商截面排名直接当信号：官方描述里不少因子已做 `CrossSectionalRank`，你必须在**当时可见股票**上自己排名。
- 不要把本目录或示例片段整段粘进 `output`。
