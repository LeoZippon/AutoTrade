# QuantsPlaybook 公式笔记

`hugo2046/QuantsPlaybook` 全仓约 613MB，未 clone。
ICU / RSRS 研报复现 / STR / 球队硬币 / 筹码分布都在带输出的 notebook 里，按任务未下载。
下面是公开研报口径的可重算式，**不是**对方笔记本的逐行复现。系数若与研报原文冲突，以你能在 PIT 下定义清楚的版本为准，并在策略注释写明。

已拉取的 SignalMaker 实现（QRS、VMACD、Alligator）以 `vendor/QuantsPlaybook/SignalMaker/` 为准，这里不重复抄代码。

## RSRS（光大）

```text
在窗口 N（常用 18）上做 OLS：High_i = α + β Low_i + e
R² 为该回归判定系数
z = (β - mean(β, M)) / std(β, M)
M 常用 600 或 1100
score_basic = z
score_right = z * R²          # 「修正标准分」
score_jq    = z * β * R²      # 聚宽社区常见
```

阈值常见 ±0.7：上穿做多，下穿空仓。
高低价用冻结 qfq。官方因子页有一处写成 `Low ~ High`，社区与 084 文章用 `High ~ Low`；改写时固定一种。
QRS（中金，已有 `qrs.py`）：同样用 high/low，β = corr * std_h / std_l，再 z；调用形如 `QRSCreator(low, high).fit(18, 600)`。

## ICU 均线（中泰 20230412，笔记本未拉）

公开描述是「用一条滞后更小的均线做绝对收益多空」，不是再造一条 MACD。
可落地、且不假装复现研报参数的写法：

```text
MA_n = SMA(close, n)          # n 常用 20/60
方向：close_{T-1} > MA_n → 风险资产满仓，否则空仓或半仓
```

若要「ICU」一点的自适应：仅在价格与均线同向时更新均线锚，反向则冻结上一次均线（类似移动止损）。这是常见改写，**不能**称为中泰原式。
不要从对方 README 抄年化数字。

## STR 凸显收益（招商 / 方正，笔记本未拉）

对回看 L 日（常用 20）：

```text
r_{i,t}  = 个股日收益
r_{m,t}  = 市场日收益（沪深300 或等权截面均值）
s_{i,t}  = |r_{i,t} - r_{m,t}| / (|r_{i,t}| + |r_{m,t}| + θ)
θ        ≈ 0.1
STR_i    = Σ_t s_{i,t} r_{i,t} / Σ_t s_{i,t}
```

行为金融含义：凸显的极端收益被投资者高估，高 STR 后续往往偏弱 → 截面上 `sign=-1`。
08:30 用到 T-1。不要用未可见的当日涨跌幅。

## 球队硬币 / 隔夜（方正 20220611，笔记本未拉）

```text
ON_t = open_t / close_{t-1} - 1
ID_t = close_t / open_t - 1
```

「球队」：ON 与 ID 同号（趋势连贯）。「硬币」：异号（隔夜与日内对打）。
常见可算因子（选一个，不要全上）：

- 隔夜动量：`ON_{T-1}` 的截面（A 股隔夜常有独立结构）。
- 硬币强度：`|ON_{T-1}| + |ID_{T-1}|` 且 `sign(ON) != sign(ID)`。
- 残差隔夜：当日截面 `ON ~ ID + 市场ON` 的残差。

08:30 没有当日开盘，最多用到 T-1 的 ON/ID。竞价域若在 09:29 之后可见，才能碰「今早隔夜」。

## 筹码（广发，笔记本未拉）

优先用事件域 `cyq_perf` 的已有汇总（成本分位、获利盘），`available_at` 在收盘后，故 08:30 用 T-1。
没有明细分价表时不要自己「还原」千档筹码。

可从日线近似、但更粗：

```text
winner_proxy = (close - low_n) / (high_n - low_n)     # n=60/120
```

这只是价格在区间中的位置，不是真筹码。获利盘极高且价格跌破均成本，常作拥挤减仓，不是单独 alpha。

## VMACD / Alligator / QRS

已在 SignalMaker：

- VMACD_MTM：成交量 MACD hist → 60 日 z → 1 日差分的 60 日和（东北证券 20240921）。
- Alligator：SMMA 鳄鱼线 + 可选 AO/MACD（招商 20240507）。
- QRS：high/low 的 β 与 z（中金 20210121）。

改写时去掉 talib，用 pandas ewm：Wilder/SMMA 的 `alpha = 1/n`。
