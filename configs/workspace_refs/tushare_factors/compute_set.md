# 40 个 PIT 安全重算因子

约定：`r` 来自 T-1 冻结 qfq 日收益。
`Turn = Volume / AShares`，或用归一化日线 `turnover_rate`（已是小数；若源值是百分数则 `/100`）。
`TTM` = 最近四个**已公告**季度之和。
合成前把因子变成「越大越做多」：`sign = +1` 保持原值，`sign = -1` 再乘 -1。
截面只用当时算得出的名字。窗口不足则该票该日为空，不要回填未来。

对照官方库时：`mom_*` ≈ `return_*d`，`vol_*` ≈ `return_std_*d`，`turn_*` ≈ `avg_turnover_*d`。官方部分因子已做截面排名或取负，这里给**原始量**，翻转列单独处理。

## 动量 mom

| 名字 | 公式 | sign | 说明 |
|---|---|---|---|
| `mom_21d` | `∏(1+r, 21) - 1` | +1 | 约 1 个月动量 |
| `mom_63d` | `∏(1+r, 63) - 1` | +1 | 约 1 季 |
| `mom_126d` | `∏(1+r, 126) - 1` | +1 | 约半年 |
| `mom_12_1` | `∏(1+r, 252) / ∏(1+r, 21) - 1` | +1 | 跳过近 1 月的 12 月动量 |
| `macd_hist` | `DIF = EMA(C,12)-EMA(C,26)`；`DEA=EMA(DIF,9)`；`hist = DIF-DEA` | +1 | C 为冻结 qfq 收盘；不要用供应商当日 MACD |
| `close_ma20` | `C / MA(C,20) - 1` | +1 | 价格相对 20 日均线 |
| `px_pos_ir60` | `x=(C-O)/(H-L)`；`mean(x,60)/std(x,60)` | +1 | 对应官方 `price_position_ir_60d`；H=L 置空 |

## 反转 rev

| 名字 | 公式 | sign | 说明 |
|---|---|---|---|
| `rev_5d` | `-(∏(1+r, 5) - 1)` | +1 | 已取负，高分=近 5 日跌得多 |
| `rsi14` | Wilder：`avg_gain/avg_loss`，`com=13` 的 EMA；`100-100/(1+RS)` | -1 | 高 RSI 偏空，翻转后再做多 |

## Alpha101 alpha

| 名字 | 公式 | sign | 说明 |
|---|---|---|---|
| `alpha101_12` | `Sign(ΔVol) * (-ΔC)` | +1 | 量增价跌为正 |
| `alpha101_101` | `(C-O) / ((H-L) + 1e-3)` | +1 | 日内位置 |
| `alpha101_6` | `-Corr(Open, Vol, 10)` | +1 | 官方已带负号 |

`Δ` 为 1 日差分。相关、符号在个股时间序列上算，不要用未可见的当日 bar。

## 风险 risk

| 名字 | 公式 | sign | 说明 |
|---|---|---|---|
| `vol_21` | `Std(r, 21)` | -1 | 高波动做空 |
| `vol_63` | `Std(r, 63)` | -1 | |
| `vol_252` | `Std(r, 252)` | -1 | |
| `beta_60_csi300` | `Cov(r, r_300, 60) / Var(r_300, 60)` | -1 | 指数用 T-1 可见 `index_daily` |
| `idio_vol_252` | `r = a + b*r_300 + e`，`Std(e, 252)` | -1 | 官方长窗是 1320 日；这里用 252 日可算 |
| `high_low_63` | `max(NAV,63) / min(NAV,63)`，`NAV=cumprod(1+r)` | -1 | 区间越宽越空 |
| `sharpe_60` | `mean(r,60) / std(r,60)` | +1 | 无风险利率取 0 |
| `downside_vol_63` | `Std(min(r, 0), 63)` | -1 | 下行波动 |

## 流动性 liq

| 名字 | 公式 | sign | 说明 |
|---|---|---|---|
| `turn_20` | `MA(Turn, 20)` | -1 | 高换手偏空 |
| `turn_63` | `MA(Turn, 63)` | -1 | |
| `bias_turn_21_252` | `MA(Turn,21)/MA(Turn,252) - 1` | -1 | 近期换手相对长期抬升 |
| `amihud_21` | `mean(\|r\| / Amount, 21)` | +1 | 非流动性溢价；金额为 0 置空 |
| `std_turn_21` | `Std(Turn, 21)` | -1 | 换手不稳 |

## 规模 size

| 名字 | 公式 | sign | 说明 |
|---|---|---|---|
| `ln_mcap` | `log(total_mv)` | -1 | SMB：小市值做多 |
| `ln_float` | `log(circ_mv)` | -1 | 流通市值 |
| `nl_size` | 当日截面 `Size^3 ~ Size` 的残差，`Size=log(total_mv)` | +1 | 非线性规模，不再二次翻转 |

官方 `size`/`float_size` 已是 `-log(MV/1e6)`。这里给原始对数，用 `sign=-1` 对齐 SMB。

## 价值 val

分子用已公告财务，分母用 T-1 市值。亏损或分母非正则置空。

| 名字 | 公式 | sign | 说明 |
|---|---|---|---|
| `ep_ttm` | `NP_parent_TTM / total_mv` | +1 | 也可用 `1/pe_ttm`（亏损 PE 为空） |
| `bp` | `SE_parent / total_mv` | +1 | 或 `1/pb` |
| `sp_ttm` | `Revenue_TTM / total_mv` | +1 | 或 `1/ps_ttm` |
| `cfp_ttm` | `OCF_TTM / total_mv` | +1 | 经营现金流/市值 |
| `dy_ttm` | 近 4 个已公告报告期现金分红 / 市值，或可见 `dv_ttm` | +1 | 分红按公告可见，不要用未除权未来预案 |

## 质量 qual

| 名字 | 公式 | sign | 说明 |
|---|---|---|---|
| `roe_ttm` | `NP_parent_TTM / Equity` | +1 | 权益用最近已公告资产负债表 |
| `roa_ttm` | `NP_TTM / TotalAssets` | +1 | |
| `gpm_ttm` | `(Revenue_TTM - Cost_TTM) / Revenue_TTM` | +1 | |
| `npm_ttm` | `NP_TTM / Revenue_TTM` | +1 | |
| `asset_turn` | `Revenue_TTM / TotalAssets` | +1 | |
| `accruals` | `-(NP_TTM - OCF_TTM) / TotalAssets` | +1 | 已取负：应计低更好 |
| `lev` | `TotalLiab / TotalAssets` | -1 | 高杠杆偏空 |

## 组合建议

等权合成前：在当时截面上对每个因子做去极值（如 1%/99%）和 z-score，再乘 `sign`，最后求和。
不要把官方库里已经 Rank 过的值再和这里的原始量混加。
合成后仍只对有限值排序，等权下单，预算留手续费和滑点缓冲。
