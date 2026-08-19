# 202 因子家族索引

来源：TuShare `factor_list`（doc_id=486），2026-08 页面。资产类型目前只有股票。
公式是供应商一行算法，不是本环境已落盘的取值。
标注 `CSRank` 的因子在官方实现里做了截面排名——你必须在当时可见股票上重做，不能读现成 rank。
标注 `官方已取负` 的因子，不要再乘一次 -1，除非你改回原始量。

## 计数

| 家族 | 个数 |
|---|---|
| Alpha101 | 31 |
| Growth | 15 |
| Liquidity | 35 |
| Momentum | 20 |
| Quality | 59 |
| Reversal | 3 |
| Risk | 25 |
| Size | 3 |
| Value | 11 |
| 合计 | 202 |

## Alpha101（31）

官方子集，不是完整 101 条。量价一律按冻结 qfq 重算；VWAP 本环境若无，可用 `(O+H+L+C)/4` 或 `Amount/Volume` 并在注释写明。

| 名字 | 公式 |
|---|---|
| `alpha101_1` | `Rank(Ts_ArgMax(SignedPower(IF(r<0, Std(r,20), C), 2), 5)) - 0.5` |
| `alpha101_2` | `-Corr(Rank(ΔLog(V),2), Rank((C-O)/O), 6)` |
| `alpha101_3` | `-Corr(Rank(O), Rank(V), 10)` |
| `alpha101_4` | `-Ts_Rank(Rank(L), 9)` |
| `alpha101_5` | `Rank(O - Mean(VWAP,10)) * (-Abs(Rank(C-VWAP)))` |
| `alpha101_6` | `-Corr(O, V, 10)` |
| `alpha101_7` | `ADV20<V ? -Ts_Rank(\|ΔC_7\|,60)*Sign(ΔC_7) : -1` |
| `alpha101_8` | `-Rank(Sum(O,5)*Sum(r,5) - Delay(that,10))` |
| `alpha101_9` | 近 5 日 ΔC 全正或全负则取 ΔC，否则 `-ΔC` |
| `alpha101_10` | 对 `alpha101_9` 的 4 日版再 `Rank` |
| `alpha101_11` | `(Rank(TsMax(VWAP-C,3))+Rank(TsMin(VWAP-C,3))) * Rank(ΔV_3)` |
| `alpha101_12` | `Sign(ΔV) * (-ΔC)` |
| `alpha101_13` | `-Rank(Cov(Rank(C), Rank(V), 5))` |
| `alpha101_14` | `-Rank(Δr_3) * Corr(O, V, 10)` |
| `alpha101_15` | `-Sum(Rank(Corr(Rank(H), Rank(V), 3)), 3)` |
| `alpha101_16` | `-Rank(Cov(Rank(H), Rank(V), 5))` |
| `alpha101_17` | `-Rank(TsRank(C,10)) * Rank(ΔΔC) * Rank(TsRank(V/ADV20,5))` |
| `alpha101_18` | `-Rank(Std(\|C-O\|,5) + (C-O) + Corr(C,O,10))` |
| `alpha101_19` | 官方长式：7 日价格方向 × 250 日收益排名，再叠加 VWAP-C 与量的相关项 |
| `alpha101_20` | `-Rank(O-Delay(H,1))*Rank(O-Delay(C,1))*Rank(O-Delay(L,1))` |
| `alpha101_22` | `-Δ(Corr(H,V,5),5) * Rank(Std(C,20))` |
| `alpha101_23` | `Mean(H,20)<H ? -ΔH_2 : 0` |
| `alpha101_25` | `Rank(-r * ADV20 * VWAP * (H-C))` |
| `alpha101_33` | `Rank(-(1-O/C))` |
| `alpha101_34` | `Rank(1-Rank(Std(r,2)/Std(r,5)) + 1-Rank(ΔC))` |
| `alpha101_41` | `sqrt(H*L) - VWAP` |
| `alpha101_52` | `(-TsMin(L,5)+Delay(TsMin(L,5),5)) * Rank((Sum(r,240)-Sum(r,20))/220) * TsRank(V,5)` |
| `alpha101_53` | `-Δ(((C-L)-(H-C))/(C-L), 9)` |
| `alpha101_54` | `(-(L-C)*O^5) / ((L-H)*C^5)` |
| `alpha101_57` | `-(C-VWAP) / DecayLinear(Rank(TsArgMax(C,30)), 2)` |
| `alpha101_101` | `(C-O)/((H-L)+0.001)` |

缺号（21/24/26–32/…）官方库未收录，不要自行补「101 全文」。

## Growth（15）

财务同比窗口官方写 252 日，PIT 下应改为「四个已公告季度之前」的同口径值，不要按日历硬取 T-252 未公告数。

| 名字 | 公式 |
|---|---|
| `peg_252d` | `PE / (EPS 同比增长率 * 100)`，`PE=C/EPS_TTM` |
| `np_ttm_qoq` | `CSRank(NP_TTM / NP_TTM_{prev} - 1)` |
| `yoy_net_profit` | `NP_t / NP_{t-252} - 1` |
| `yoy_ocf` | `CSRank(OCF_TTM / OCF_TTM_{t-252} - 1)` |
| `sa` | `SPS=OR_Q/Shares`；`SG=SPS/SPS_{t-252}-1`；`CSRank(SG-SG_{t-63})` |
| `gross_margin_qoq` | `CSRank(GPM_TTM / GPM_TTM_{t-63} - 1)` |
| `pa` | `PG=ROA-ROA_{t-252}`；`CSRank(PG-PG_{t-63})` |
| `yoy_roa` | `CSRank(ROA_TTM / ROA_TTM_{t-252} - 1)` |
| `yoy_net_asset` | `CSRank(Equity / Equity_{t-252} - 1)` |
| `yoy_revenue` | `OR_t / OR_{t-252} - 1` |
| `yoy_roe` | `CSRank(ROE_TTM / ROE_TTM_{t-252} - 1)` |
| `yoy_total_asset` | `CSRank(TA / TA_{t-252} - 1)` |
| `eaa` | `EGA=EPS_Q/EPS_Q_{t-252}-1`；`CSRank(EGA-EGA_{t-63})` |
| `eap` | `EGP=(EPS_Q-EPS_Q_{t-252})/C`；`CSRank(EGP-EGP_{t-63})` |
| `asset_growth_qoq` | `CSRank(TA / TA_{prev} - 1)` |

## Liquidity（35）

`DailyTurnover = Volume / AShares`。`w=k*21` 表示 k 个月交易日。

| 名字 | 公式 |
|---|---|
| `avg_turnover_5d` | `MA(Turn, 5)` |
| `avg_turnover_10d` | `MA(Turn, 10)` |
| `avg_turnover_20d` | `MA(Turn, 20)` |
| `amount_ma_20d` | `MA(Amount, 20)` |
| `turnover_ma_20d` | 官方已取负：`-MA(V/FloatMV, 20)` |
| `sum_abs_rtn_amount_20d` | `Sum(\|r\|,20) / Sum(Amount,20)` |
| `turnover_ma_20d_120d` | 官方已取负：`-MA(V/FloatMV,20) / MA(V/FloatMV,120)` |
| `avg_turnover_21d` | `MA(Turn, 21)` |
| `std_turnover_21d` | `Std(Turn, 21)` |
| `bias_std_turn_21d_252d` | `Std(Turn,21)/Std(Turn,252) - 1` |
| `bias_turn_21d_252d` | `MA(Turn,21)/MA(Turn,252) - 1` |
| `bias_std_turn_21d_504d` | `Std(Turn,21)/Std(Turn,504) - 1` |
| `bias_turn_21d_504d` | `MA(Turn,21)/MA(Turn,504) - 1` |
| `std_turnover_42d` | `Std(Turn, 42)` |
| `avg_turnover_42d` | `MA(Turn, 42)` |
| `bias_turn_42d_252d` | `MA(Turn,42)/MA(Turn,252) - 1` |
| `bias_std_turn_42d_252d` | `Std(Turn,42)/Std(Turn,252) - 1` |
| `bias_std_turn_42d_504d` | `Std(Turn,42)/Std(Turn,504) - 1` |
| `bias_turn_42d_504d` | `MA(Turn,42)/MA(Turn,504) - 1` |
| `std_turnover_63d` | `Std(Turn, 63)` |
| `avg_turnover_63d` | `MA(Turn, 63)` |
| `bias_turn_63d_252d` | `MA(Turn,63)/MA(Turn,252) - 1` |
| `bias_std_turn_63d_252d` | `Std(Turn,63)/Std(Turn,252) - 1` |
| `bias_std_turn_63d_504d` | `Std(Turn,63)/Std(Turn,504) - 1` |
| `bias_turn_63d_504d` | `MA(Turn,63)/MA(Turn,504) - 1` |
| `avg_turnover_126d` | `MA(Turn, 126)` |
| `std_turnover_126d` | `Std(Turn, 126)` |
| `bias_turn_126d_252d` | `MA(Turn,126)/MA(Turn,252) - 1` |
| `bias_std_turn_126d_252d` | `Std(Turn,126)/Std(Turn,252) - 1` |
| `bias_turn_126d_504d` | `MA(Turn,126)/MA(Turn,504) - 1` |
| `bias_std_turn_126d_504d` | `Std(Turn,126)/Std(Turn,504) - 1` |
| `std_turnover_252d` | `Std(Turn, 252)` |
| `avg_turnover_252d` | `MA(Turn, 252)` |
| `volume_alpha_300d_000001` | 5 日量动量对上证做 300 日 OLS 的截距 |
| `volume_alpha_300d_000300` | 同上，对标沪深300 |

## Momentum（20）

| 名字 | 公式 |
|---|---|
| `return_5d` | `∏(1+r,5)-1` |
| `ma_20d` | `MA(C,20)` |
| `return_21d` | `∏(1+r,21)-1` |
| `return_42d` | `∏(1+r,42)-1` |
| `price_position_ir_60d` | `mean((C-O)/(H-L),60) / std(...)` |
| `return_63d` | `∏(1+r,63)-1` |
| `alpha_125d_000300` | 对沪深300 日收益 125 日 OLS 截距 |
| `return_126d` | `∏(1+r,126)-1` |
| `alpha_250d_000300` | 250 日截距 |
| `return_252d` | `∏(1+r,252)-1` |
| `alpha_500d_000300` | 500 日截距 |
| `alpha_528d_000001` | 对上证 528 日截距 |
| `alpha_792d_000001` | 792 日截距 |
| `alpha_1000d_000300` | 1000 日截距 |
| `alpha_1320d_000001` | 1320 日截距 |
| `rsrs` | `High~Low` 或官方页面写 `Low~High` 的 18 日 β，再对 β 做 200 日 z；社区常用 `High~Low` |
| `MACD` | `2*(DIF-DEA)`，12/26/9 |
| `dif` | `EMA(C,12)-EMA(C,26)` |
| `dea` | `EMA(DIF,9)` |
| `days_down_up` | `\|连涨天数 - 连跌天数 - 1\|` |

长窗 Alpha/Beta 在短 Validation 里往往算不满，空值即可，不要缩短窗口假装满样本。

## Quality（59）

| 名字 | 公式 |
|---|---|
| `roe_ttm_lag63d` | `ROE_TTM` 再滞后 63 日（官方默认 lag 可 0） |
| `debt_asset_ratio` | `TL/TA` |
| `eps_ttm` | `CSRank(EPS)` |
| `financial_leverage` | `CSRank(TA/Equity)` |
| `gpm_ttm` | `CSRank((OR-Cost)/OR)` TTM |
| `icr` | `CSRank(EBIT_TTM / Interest_TTM)` |
| `income_tax_yoy` | `CSRank(所得税TTM 同比)` |
| `np_to_inventory_yoy` | `CSRank((NP_Q/Inv) 同比)` |
| `npm_q` | `CSRank(NP/OR)` 单季 |
| `quality_composite` | AQR 风格 6 项盈利/现金比率之和，忽略 inf |
| `ar_ap_to_revenue` | `CSRank((预收-预付)/OR)` |
| `asset_turnover` | `CSRank(OR_TTM / TA)` |
| `delta_current_ratio` | `CSRank(CR - CR_{t-252})` |
| `delta_de` | `CSRank(DE - DE_{t-252})` |
| `gpm_q` | `CSRank(GPM)`（官方描述仍写 TTM 口径） |
| `cash_profit_ratio` | `CSRank((OCF_TTM-NP_TTM)/NP_TTM)` |
| `delta_opm` | `CSRank(OPM - OPM_{t-252})` |
| `eps_q` | `CSRank(单季 EPS)` |
| `eps_y` | `CSRank(年度 EPS)` |
| `delta_npm` | `CSRank(NPM - NPM_{t-252})` |
| `market_value_leverage` | `CSRank((MV - 非流动负债)/MV)` |
| `npm_y` | `CSRank(年度 NPM)` |
| `opm_y` | `CSRank(年度 OPM)` |
| `quick_ratio` | `(CA-Inv)/CL` |
| `delta_gpm` | `CSRank(GPM - GPM_{t-252})` |
| `gpm_y` | `CSRank(年度 GPM)` |
| `np_to_total_expenses_yoy` | `CSRank(NP/三费 同比)` |
| `np_to_deferred_tax_yoy` | `CSRank(NP/递延所得税资产 同比)` |
| `roe_y` | 年度 ROE |
| `roa_q` | `CSRank(NP/TA)` 单季 |
| `gpm_qoq` | `CSRank(GPM_TTM / GPM_{t-63} - 1)` |
| `delta_inventory_turnover` | `CSRank(IT - IT_{t-252})` |
| `delta_roa` | `CSRank(ROA - ROA_{t-252})` |
| `fixed_asset_turnover` | `CSRank(OR_TTM / FA)` |
| `npm_ttm` | `CSRank(NP/OR)` TTM |
| `opm_ttm` | `CSRank(OP/OR)` TTM |
| `receivable_turnover` | `CSRank(OR_TTM / AR)` |
| `cfcr` | `CSRank(OCF_TTM / Interest_TTM)` |
| `delta_cash_ratio` | `CSRank(CashRatio - CashRatio_{t-252})` |
| `lra_yoy` | `CSRank(长期应收 同比)` |
| `np_to_fixed_assets_yoy` | `CSRank(NP/FA 同比)` |
| `np_to_salary_yoy` | `CSRank(NP_TTM/职工薪酬TTM 同比)` |
| `npm_q_qoq` | `CSRank(单季 NPM 环比)` |
| `npm_tsh` | `CSRank(NP_parent_TTM / 平均股本)` |
| `npm_ttm_qoq` | `CSRank(NPM_TTM / NPM_{t-63} - 1)` |
| `cash_ratio` | `CSRank((货币+交易性资产)/流动负债)` |
| `current_ratio` | `CA/CL` |
| `de` | `TL/Equity` |
| `delta_asset_turnover` | `CSRank(AT - AT_{t-252})` |
| `delta_quick_ratio` | `CSRank(QR - QR_{t-252})` |
| `delta_roe` | `CSRank(ROE - ROE_{t-252})` |
| `inventory_turnover` | `CSRank(Cost_TTM / Inv)` |
| `roa_ttm` | `CSRank(NP/TA)` TTM |
| `roe_ttm` | `NP_parent / Equity` TTM |
| `tax_surcharge_yoy` | `CSRank(税金及附加TTM 同比)` |
| `equity_turnover` | `CSRank(OR_TTM / Equity)` |
| `expenses_to_equity_yoy` | `CSRank(三费/净资产 同比)` |
| `roa_y` | `CSRank(年度 ROA)` |
| `opt_tpro` | `CSRank(营业利润_Q / 利润总额_Q)` |

## Reversal（3）

| 名字 | 公式 |
|---|---|
| `small_cap_reversal_21d` | 小市值子集上 `CSRank(-(∏(1+r,21)-1))` 再归一 |
| `rsi` | Wilder RSI(14) |
| `price_dist` | 距下一心理整数的距离：`<10` 用整数，`[10,100)` 用 10 的倍数，`≥100` 用 100 的倍数 |

## Risk（25）

| 名字 | 公式 |
|---|---|
| `days_beyond_upper_lower_21d` | 21 日内 `z>1` 天数减 `z<-1` 天数，`z=(C-MA)/Std` |
| `return_std_21d` | `Std(r, 21)` |
| `high_low_21d` | `max(NAV,21)/min(NAV,21)` |
| `high_low_42d` | 42 日高低比 |
| `return_std_42d` | `Std(r, 42)` |
| `sharpe_60d` | `mean(r,60)/std(r,60)` |
| `beta_60d_000300` | 60 日对沪深300 β |
| `return_std_63d` | `Std(r, 63)` |
| `high_low_63d` | 63 日高低比 |
| `volume_beta_120d_000300` | 5 日量动量对沪深300 的 120 日 β |
| `beta_125d_000300` | 125 日 β |
| `high_low_126d` | 126 日高低比 |
| `return_std_126d` | `Std(r, 126)` |
| `beta_250d_000300` | 250 日 β |
| `return_std_252d` | `Std(r, 252)` |
| `high_low_252d` | 252 日高低比 |
| `beta_500d_000300` | 500 日 β |
| `sharpe_750d` | `mean(r,750)/std(r,750)` |
| `adjusted_sharpe_750d` | `mean(r,750) / std(r,750)^4` |
| `beta_1000d_000300` | 1000 日 β |
| `sigma_1320d_000001` | 对上证 1320 日残差波动 |
| `beta_1320d_000001` | 对上证 1320 日 β |
| `beta_consistency_1320d_000300` | `Std(β * residual, 1320)` 对沪深300 |
| `sigma_1320d_000300` | 对沪深300 1320 日残差波动 |
| `log_price` | `log(C)` |

## Size（3）

| 名字 | 公式 |
|---|---|
| `float_size` | `-log(FloatShares * C / 1e6)`（官方已取负） |
| `nl_size` | 截面 `Size^3 ~ Size` 残差 |
| `size` | `-log(TotalShares * C / 1e6)`（官方已取负） |

## Value（11）

| 名字 | 公式 |
|---|---|
| `dividend_yield_3y_avg` | `Sum(每股现金分红, 735) / 3 / C` |
| `pegh5` | 官方已取负：`-CSRank(C / (5年EPS复合增速 * EPS_TTM))` |
| `etp5` | `CSRank(Mean(年度NP,1260) / Mean(MV,1260))` |
| `ncf_to_market` | `(筹资+投资+经营净现金流 TTM) / MV` |
| `fcf_to_market` | `(OCF_TTM - 投资现金流出_TTM) / MV` |
| `ebitda_to_market` | `EBITDA / MV` |
| `earnings_to_price` | `NP_parent_TTM / MV` |
| `book_to_market` | `(SE_parent + 递延所得税资产) / MV` |
| `earnings_cut_to_market` | `扣非NP_TTM / MV`（缺字段时官方用归母净利替代，须注明） |
| `ocf_to_market` | `OCF_TTM / MV` |
| `sales_to_market` | `OR_Q / MV`（官方用单季收入，不是 TTM） |
