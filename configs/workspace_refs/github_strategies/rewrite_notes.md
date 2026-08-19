# 改写成 generate_orders

正式策略只有：

```python
def generate_orders(context):
    return []
```

合法 import：`__future__`、`collections`、`datetime`、`decimal`、`math`、`statistics`、`numpy`、`pandas`。
读数只能 `pandas.read_parquet` 且第一参数直接挂在 `context.snapshot_dir` 或 `context.asof_dir` 下。
订单：`symbol`、`action`∈{buy,sell}、正整数 `quantity`、`execute_at >= inference_at`。
等权时按 `sorted(symbols)` 分配预算，集合迭代顺序不是信号。

## 时间对照

| 平台习惯 | 本环境 |
|---|---|
| 聚宽 `run_daily(..., '09:30')` / 开盘 | `inference_time=08:30`，订单 `execute_at` 当天 `09:30`（用日线 open） |
| 聚宽 `14:00`/`14:50` 尾盘 | 当天 `15:00`（用日线 close）；08:30 推断看不到当日盘中价 |
| 聚宽 `attribute_history(..., count=N)` | `asof_dir/daily` 截每票最后 N 根 **已可见** 行 |
| 模块全局 `g.hold_list` | 禁止当记忆。持仓用 `context.account.positions`；「本周是否已调」用日期从 PIT 重算 |
| `order_target_value` | 自己算股数：100 的倍数，留佣金/印花税/滑点 |

## 1. 小市值

对照：`vendor/CTBZStock/.../small_cap_demo.py`，`vendor/ashare-quant-strategies/articles/048_*`。
规则：T-1 流通或总市值升序，滤 ST/停牌/上市不足 N 日/价格过低；持 5–10 只等权。
CTBZ 回测里用「次日快照」过滤开盘涨跌停——08:30 **没有**次日开盘，改成：买单仍发 `09:30`，涨停由 Broker 拒单；或用 T-1 收盘是否贴近涨停价作软过滤。
不要 `code.startswith` 写死后忘了 `.SZ/.SH` 后缀：本环境代码是 `000001.SZ`。

## 2. 基本面小市值

对照：`articles/077_*`。
在小市值候选上再要：已公告收入同比、净利同比下限。
原文 `get_fundamentals` + `9:15` 选股在本环境不存在；月频或每 10–20 日在 08:30 用 fundamentals 域过滤。
黑名单、动态仓位计数器全部丢掉，改成无状态漏斗。

## 3. 高股息低波动

对照：`articles/006_*`。
近 1 年已公告现金分红 / T-1 市值，再在高股息子集里取低波动、低负债。
原文周频 `9:30` 调仓 + `14:00` 检查涨停：08:30 一次推断里完成筛选；涨停股若已持有，卖单用 `09:30` 看能否打开。
`finance.STK_XR_XD` 换成可见分红表或 `dv_ttm`，不要用未公告预案。

## 4. CST：EP + 低波 + 动量

对照：`vendor/Cheap-Stable-Trending-quant/docs/CURRENT-STRATEGY.md` 与 `results/P5-*.py`。
三因子等权 z：`EP = 已公告净利/市值`，`LowVol = -Std(r,40或60)`，`MOM = P_{t-21}/P_{t-61} - 1`（他们的 40 日窗，不是美股 12-1）。
股票池：非 ST、上市满 1 年、可再滤金融与低成交额。
原文季度调仓（5/9/11 月第一个交易日）；本环境用 `period=month` 或自己判断月份切换。
文档收益数字不要写进策略注释当预期。聚宽 API 全部删掉。

## 5. ETF 双动量 / 多资产轮动

对照：`articles/003_*`、`articles/043_*`。
对每只**快照里真实存在**的 ETF：`log(close)` 对时间回归，`score = (e^{slope*250}-1) * R²`，持有最高 1–2 只。
`513100` 等海外 ETF 不在数据里就从池子删除，不要用指数代替。
窗 25 日；08:30 用 T-1 收盘序列。每天轮动摩擦大，可改周频。

## 6. RSRS

对照：`articles/084_*`，以及因子包 `rsrs`。
`High = a + β Low`，N=18；β 的 z 窗用 600（原文 084 用 600，聚宽种子常用 1100）。
`score = z * β * R²`，>0.7 开多 ETF，<-0.7 清仓。
择时标的用 300 指数日线，下单用 `510300.SH`（以 universe 实际代码为准）。
M 不足时空仓。不要把斜率序列存在模块里跨阶段用——每次从尾窗重算。

## 7. ICU-MA

对照：`playbook_notes.md`（笔记本未拉）。
指数或 ETF：收盘相对 ICU 均线的多空。08:30 用 T-1。
不要复现中泰研报的宣传曲线；只保留「均线多空开关」接到仓位 0/1 或 0/0.5/1。

## 8. Alligator

对照：`vendor/QuantsPlaybook/SignalMaker/alligator_indicator_timing.py`。
中价 `(H+L)/2` 的 SMMA 13/8/5，并移位 8/5/3。
三线开口且价格在唇线之上做多，缠绕或翻下清仓。
该文件还带 AO、MACD 辅助；正式策略只留一条规则。talib 不能 import，SMMA 自己写。

## 9. VMACD

对照：`vmacd_mtm.py`。
对**成交量**做 MACD(12,26,9) 取 hist，再 60 日 z-score，再 `diff` 的 60 日和。
用作指数/ETF 择时，不要对全市场每票算一遍除非你截了尾窗。
量用归一化 `vol`（股）。

## 10. STR（凸显）

对照：`playbook_notes.md`。
个股收益相对市场的凸显度加权平均，高 STR 常作空头因子（彩票偏好）。
08:30 用 T-1 截面收益。θ、回看窗写进注释。缺市场收益就用中证全指或沪深300 可见收益。

## 11. 隔夜 / 球队硬币

对照：`playbook_notes.md`。
`ON = open_t/close_{t-1}-1`，`ID = close_t/open_t-1`。
08:30 **没有当日 open**：隔夜因子只能用到 T-1 的 ON/ID。
不要用「今天集合竞价」除非 auction 域已可见且你把推断放到 09:29 之后。
做多隔夜残差低、或硬币（ON 与 ID 反向）的一侧时，先在注释写清方向，再截面排序。

## 12. Alpha101 截面

对照：`vendor/WorldQuant_alpha101_code/*.py`，`vendor/alpha191/alpha191.py`，因子包三条。
先实现 `alpha101_101`、`alpha101_12`、`alpha101_6` 的截面 z 合成。
源码里的 pandas 面板函数要改成按 `ts_code` groupby 的有限尾窗。
191/101 不要全算；正式回放 30 秒预算扛不住。

## 通用删减

- 删 `jqdata`/`talib`/`loguru`/`Simulation`/`get_current_data`。
- 删滑点/佣金自己撮合：Broker 已收。
- 删未来函数：`get_price(..., 当天分钟)`、次日开盘过滤。
- 删打印与回测曲线。
- 候选、卖出、买入三步：先卖不在目标里的持仓，再按排序买新票，现金一次快照递减。
