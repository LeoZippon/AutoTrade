# 社区/官方策略思路（只读）

这些文件只是参考，正式策略必须写到 `/mnt/agent/workspace/output/main.py`。
禁止把整棵参考树拷进 `output`；禁止在正式策略里写死 `/mnt/agent/workspace`。
正式回放只能 `numpy`/`pandas` + 单文件；用 PIT：`available_at <= inference_at`；默认 `08:30` 只能用 T-1 日线。
财务用公告日/`available_at`，不用 `end_date` 偷看。

## 任务

在这些社区策略的**机制**上改写和优化，不要原样调用聚宽 / 米筐 / 同花顺 / BigQuant / 掘金 API。
平台里的 `get_fundamentals`、`attribute_history`、`order_target`、`run_daily` 在本环境都不存在。
正式入口只有 `generate_orders(context)`，返回严格 JSON 订单数组。

## 来源完整度（诚实）

| 来源 | 本包依据 | 限制 |
|---|---|---|
| 聚宽 JoinQuant | 公开流传的社区写法与因子规则 | 站点当时 geo-blocked，**没有**从 joinquant.com 拉回策略正文 |
| 米筐 RiceQuant | 官方文档「策略实例」页 | 黄金交叉 20/120、MACD 12/26/9、RSI 14 阈值 85/30、海龟 55/20；股指期货例已丢弃 |
| BigQuant | 公开 Wiki 对 Graham / 小市值的描述 | 无平台回测账单 |
| 掘金 myquant | 官方示例策略页 | 期货例（双均线/Dual Thrust/R-Breaker/菲阿里）整类跳过；保留股票小市值、布林均值回归、Lynch/ROE 思路 |
| 同花顺 SuperMind | 无 | SPA 没有可恢复的策略正文，不要假装读过 |

不要发明收益率。社区帖里的「年均 18%」、集智象一类宣传数字**未核实**，本包不转载为事实。
米筐/掘金页面上的单段回测表只说明「对方平台某次演示」，不能当本环境 Validation 预期。

## 本包文件

| 文件 | 用途 |
|---|---|
| `seed_pack.md` | 12 个建议先改写的种子：信号、旋钮、PIT、改写要点 |
| `catalog.md` | 约 40 条可用思路的一页一块目录 |

先读 `seed_pack.md`，需要对照变体再翻 `catalog.md`。
