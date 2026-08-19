# 84、RSRS 动量与斜率择时策略

# 策略概述

**RSRS 动量与斜率择时策略** 是一种结合动量指标和 RSRS（相对强弱指标斜率标准化）进行 ETF 资产择时的策略。该策略通过对指定 ETF 的动量（收益率斜率）进行排序，选取最具动量的 ETF 进行投资，并通过 RSRS 指标进行市场择时，以确定何时买入、持有或清仓。

策略详细介绍

  1. **策略思想** ：

     * 策略通过动量指标（过去 20 日的收益率斜率）选取表现最好的 ETF 作为投资目标。

     * 同时利用 RSRS 指标进行市场择时，判断当前市场是否适合进行交易。如果 RSRS 指标显示市场处于强势，策略会买入或持有 ETF，否则清仓。

  2. **关键要素** ：

     * **动量指标** ：根据 ETF 的过去 20 日收益率的斜率，选择斜率最大的 ETF 作为优选目标。

     * **RSRS 指标** ：通过计算市场指数（如沪深 300 指数）的高低点线性回归斜率，并对其进行标准化处理，以确定市场的强弱。

# 策略代码与功能说明

1\. 初始化函数与全局变量设置 (initialize)

```python
def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0.001))
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='fund')
    log.set_level('order', 'error')
    # 选股池设置
    g.stock_pool = [
        '510050.XSHG',  # 上证50ETF
        '159928.XSHE',  # 中证消费ETF
        '510300.XSHG',  # 沪深300ETF
        '159949.XSHE',  # 创业板50ETF
    ]
    g.stock_num = 1  # 持仓股票数
    g.momentum_day = 20  # 动量计算的天数
    g.ref_stock = '000300.XSHG'  # 择时基础数据使用沪深300指数
    g.N = 18  # 计算斜率的天数
    g.M = 600  # 计算标准分zscore的天数
    g.score_threshold = 0.7  # RSRS标准分的阈值
    g.mean_day = 30  # 计算均线的天数
    g.mean_diff_day = 2  # 均线的差异天数
    # 初始化斜率序列
    g.slope_series = initial_slope_series()[:-1]  # 除去第一天，避免重复
    run_daily(my_trade, time='9:30', reference_security='000300.XSHG')
    run_daily(check_lose, time='open', reference_security='000300.XSHG')
    run_daily(print_trade_info, time='15:30', reference_security='000300.XSHG')
```

  * **功能说明** : 初始化策略参数，包括 ETF 池、动量天数、RSRS 计算的相关参数，并设定每日运行的交易逻辑。

  * **关键逻辑** :

    * 通过 set_option 和 set_order_cost 设定策略执行时的基本参数，如真实价格交易和交易成本。

    * run_daily 用于设定每日运行的主要交易函数和日志打印。

2\. 动量计算与 ETF 排名 (get_rank)

```python
def get_rank(context,stock_pool):
    rank = []
    for stock in g.stock_pool:
        data = attribute_history(stock, g.momentum_day, '1d', ['close'])
        score = np.polyfit(np.arange(len(data)), data.close / data.close[0], 1)[0]
        rank.append([stock, score])
    rank.sort(key=lambda x: x[-1], reverse=True)
    log.info(data.tail(3))
    return rank[0]
```

  * **功能说明** : 通过计算每个 ETF 的动量（即过去 20 天收益率的斜率），将 ETF 按动量排序，返回动量最大的 ETF。

  * **关键逻辑** :

    * np.polyfit 用于计算收益率斜率。

    * 返回排名第一的 ETF，即动量最大的 ETF。

3\. RSRS 指标计算与择时信号 (get_timing_signal)

```python
def get_timing_signal(context, stock):
    g.mean_diff_day = 5
    close_data = attribute_history(g.ref_stock, g.mean_day + g.mean_diff_day, '1d', ['close'])
    high_low_data = attribute_history(g.ref_stock, g.N, '1d', ['high', 'low'])
    intercept, slope, r2 = get_ols(high_low_data.low, high_low_data.high)
    g.slope_series.append(slope)
    rsrs_score = get_zscore(g.slope_series[-g.M:]) * r2
    if rsrs_score > g.score_threshold: return "BUY"
    elif rsrs_score < -g.score_threshold: return "SELL"
    else: return "KEEP"
```

  * **功能说明** : 通过计算沪深 300 指数的 RSRS 指标，判断当前市场状态，给出买入、卖出或持有的信号。

  * **关键逻辑** :

    * get_ols 用于计算高低点回归的斜率。

    * get_zscore 进行斜率标准化处理，并乘以拟合优度 r2 来生成 RSRS 指标。

4\. 交易执行逻辑 (my_trade)

```python
def my_trade(context):
    hour = context.current_dt.hour
    minute = context.current_dt.minute
    if hour == 9 and minute == 30:
        check_out_list = get_rank(context, g.stock_pool)
        timing_signal = get_timing_signal(context, g.ref_stock)
        print('今日自选及择时信号:{} {}'.format(check_out_list, timing_signal))
        if timing_signal == 'SELL':
            for stock in context.portfolio.positions:
                position = context.portfolio.positions[stock]
                close_position(position)
        elif timing_signal == 'BUY' or timing_signal == 'KEEP':
            adjust_position(context, check_out_list)
        else: pass
```

  * **功能说明** : 每日交易主函数，根据动量和择时信号决定 ETF 的买卖操作。

  * **关键逻辑** :

    * 如果信号为 SELL，则清仓所有持有的 ETF；如果为 BUY 或 KEEP，则调整持仓。

5\. 平仓与调仓操作 (adjust_position)

```python
def adjust_position(context, buy_stocks):
    for stock in context.portfolio.positions:
        if stock not in buy_stocks:
            log.info("[%s]已不在应买入列表中" % (stock))
            position = context.portfolio.positions[stock]
            close_position(position)
        else:
            log.info("[%s]已经持有无需重复买入" % (stock))
    position_count = len(context.portfolio.positions)
    if g.stock_num > position_count:
        value = context.portfolio.cash / (g.stock_num - position_count)
        for stock in buy_stocks:
            if context.portfolio.positions[stock].total_amount == 0:
                if open_position(stock, value):
                    if len(context.portfolio.positions) == g.stock_num:
                        break
```

  * **功能说明** : 根据最新的择时信号和目标 ETF 调整当前持仓，进行买卖操作。

  * **关键逻辑** :

    * 对不在买入列表中的持仓进行平仓操作；对需要买入的 ETF 进行开仓。

6\. 打印交易信息 (print_trade_info)

```python
def print_trade_info(context):
    trades = get_trades()
    for _trade in trades.values():
        print('成交记录：' + str(_trade))
    print('———————————————————————————————————————分割线————————————————————————————————————————')
```

  * **功能说明** : 打印每日交易的记录，用于检查策略执行的情况。

### 总结

**RSRS 动量与斜率择时策略** 通过动量与 RSRS 指标的结合，进行 ETF 的择时交易。动量指标帮助策略选择当前市场表现最好的 ETF，RSRS 指标则用于判断市场的整体强弱，从而决定是否进入或退出市场。此策略适用于那些希望通过动量和市场状态进行投资决策的投资者，同时通过适当的止损设置，控制了策略的回撤风险。

免责声明

本文所发布的所有内容仅供参考和技术研究，所提供的投资策略、分析和观点并不构成任何形式的投资建议。投资涉及风险，读者应根据自身的投资目标、风险承受能力及财务状况，独立做出决策。我们不对任何因文章内容而产生的投资损失或其他风险后果负责。请在投资前咨询专业的财务顾问或投资专家。
