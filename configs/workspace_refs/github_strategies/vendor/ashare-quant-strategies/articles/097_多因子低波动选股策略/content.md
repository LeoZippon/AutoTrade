# 97、多因子低波动选股策略

# 策略概述

**多因子低波动选股策略** 是一种基于多因子选股方法的策略，通过筛选具有稳定财务指标和低波动特征的股票，构建稳健的投资组合。策略利用ROA（资产回报率）、每股留存收益和非线性市值等因子对股票进行筛选，并结合价格波动性和流动性等因素进行进一步过滤，从而选择出在不同市场环境下表现较好的股票。此策略适合在震荡市场中寻求稳健收益的投资者。

# 策略详细介绍

  1. **策略思想** ：

     * **多因子筛选** ：结合多种财务指标，如ROA、每股留存收益、非线性市值等，进行综合选股，以确保选择的股票具有稳健的财务表现。

     * **低波动性** ：策略特别关注股票的波动性，通过过滤涨跌停的股票及其他高风险股票，降低组合的整体波动。

     * **动态调仓** ：定期调整持仓，剔除不符合条件的股票，并加入新的优质标的，保持组合的高质量和低风险。

  2. **策略代码与功能说明**

1\. 初始化函数 (initialize)

```python
def initialize(context):
    # 设定基准
    set_benchmark('000905.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(0))
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='fund')
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    # 初始化全局变量
    g.stock_num = 10  # 持股数量
    g.limit_days = 20  # 持有天数
    g.limit_up_list = []  # 涨停股票列表
    g.hold_list = []  # 持仓股票列表
    g.history_hold_list = []  # 历史持仓股票列表
    g.not_buy_again_list = []  # 禁止再买入的股票列表
    # 设置交易时间，每天运行
    run_daily(prepare_stock_list, time='9:05', reference_security='000300.XSHG')
    run_weekly(weekly_adjustment, weekday=1, time='9:40', reference_security='000300.XSHG')
    run_daily(check_limit_up, time='14:00', reference_security='000300.XSHG')
    run_daily(print_position_info, time='15:10', reference_security='000300.XSHG')
```

  * **功能说明** : 初始化策略，设定基准、交易成本、滑点和日志等级，并设置每日和每周的交易调度。

  * **关键逻辑** : 确保策略运行时环境的稳定性和交易成本的可控性，为后续策略逻辑的执行提供支持。

2\. 选股模块 (get_stock_list)

```python
def get_stock_list(context):
    yesterday = context.previous_date
    initial_list = get_all_securities().index.tolist()
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_st_stock(initial_list)
    initial_list_1 = filter_new_stock(context, initial_list, 250)
    # 筛选长期资产回报率小的股票
    roa_list = get_filtered_stocks(context, initial_list_1, 'roa_ttm_8y', 0.1)
    # 筛选每股留存收益小的股票
    reps_list = get_filtered_stocks(context, initial_list_1, 'retained_earnings_per_share', 0.1)
    # 筛选非线性市值小的股票
    initial_list_2 = filter_new_stock(context, initial_list, 125)
    nls_list = get_filtered_stocks(context, initial_list_2, 'non_linear_size', 0.1)
    # 并集去重
    union_list = list(set(roa_list).union(set(reps_list)).union(set(nls_list)))
    q = query(valuation.code, valuation.circulating_market_cap).filter(valuation.code.in_(union_list)).order_by(valuation.circulating_market_cap.asc())
    df = get_fundamentals(q, date=yesterday)
    final_list = list(df.code)
    return final_list
```

  * **功能说明** : 根据多个因子筛选出目标股票池，包括长期资产回报率、每股留存收益和非线性市值等，最终获取低波动性且具有稳健财务表现的股票列表。

  * **关键逻辑** :

    * 通过多因子筛选结合流动性和市值等指标，确保所选股票在财务上稳健并具有投资价值。

3\. 持仓调整模块 (weekly_adjustment)

```python
def weekly_adjustment(context):
    target_list = get_stock_list(context)
    target_list = filter_paused_stock(target_list)
    target_list = filter_limitup_stock(context, target_list)
    target_list = filter_limitdown_stock(context, target_list)
    # 过滤最近买入且涨停过的股票
    recent_limit_up_list = get_recent_limit_up_stock(context, target_list, g.limit_days)
    black_list = list(set(g.not_buy_again_list).intersection(set(recent_limit_up_list)))
    target_list = [stock for stock in target_list if stock not in black_list]
    # 调仓操作
    adjust_position(context, target_list, g.stock_num)
```

  * **功能说明** : 每周调整持仓，根据最新选股结果，卖出不符合条件的股票，并买入新的目标股票。

  * **关键逻辑** :

    * 动态调仓，确保投资组合始终保持在低波动且高质量的股票中，减少市场波动的影响。

4\. 涨停检查与调仓函数 (check_limit_up)

```python
def check_limit_up(context):
    now_time = context.current_dt
    if g.high_limit_list != []:
        for stock in g.high_limit_list:
            current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close','high_limit'], count=1)
            if current_data.iloc[0,0] < current_data.iloc[0,1]:
                log.info("[%s]涨停打开，卖出" % (stock))
                position = context.portfolio.positions[stock]
                close_position(position)
            else:
                log.info("[%s]涨停，继续持有" % (stock))
```

  * **功能说明** : 检查持仓中昨日涨停的股票，如果涨停打开则卖出，如果继续涨停则持有。

  * **关键逻辑** :

    * 对涨停股票进行动态管理，避免在涨停打开时继续持有造成损失，同时在涨停延续时获取更多收益。

5\. 交易模块

```python
def adjust_position(context, buy_stocks, stock_num):
    for stock in context.portfolio.positions:
        if stock not in buy_stocks:
            log.info("[%s]不在应买入列表中" % (stock))
            position = context.portfolio.positions[stock]
            close_position(position)
        else:
            log.info("[%s]已经持有无需重复买入" % (stock))
    position_count = len(context.portfolio.positions)
    if stock_num > position_count:
        value = context.portfolio.cash / (stock_num - position_count)
        for stock in buy_stocks:
            if context.portfolio.positions[stock].total_amount == 0:
                open_position(stock, value)
```

  * **功能说明** : 根据调整后的持仓目标，对持仓股票进行卖出和买入操作，确保持仓组合符合预期的数量和质量。

  * **关键逻辑** :

    * 动态管理持仓比例，确保在目标股票池中持仓数量与投资策略一致，保持组合的高质量和低风险。

6\. 打印持仓信息 (print_position_info)

```python
def print_position_info(context):
    trades = get_trades()
    for _trade in trades.values():
        print('成交记录：'+str(_trade))
    for position in list(context.portfolio.positions.values()):
        securities=position.security
        cost=position.avg_cost
        price=position.price
        ret=100*(price/cost-1)
        value=position.value
        amount=position.total_amount
        print('代码:{}'.format(securities))
        print('成本价:{}'.format(format(cost,'.2f')))
        print('现价:{}'.format(price))
        print('收益率:{}%'.format(format(ret,'.2f')))
        print('持仓(股):{}'.format(amount))
        print('市值:{}'.format(format(value,'.2f')))
```

  * **功能说明** : 打印每日持仓和交易信息，帮助投资者了解每日交易详情及持仓情况。

  * **关键逻辑** :

    * 提供清晰的持仓和交易记录，有助于投资者实时监控投资组合的表现。

### 总结

**多因子低波动选股策略** 通过综合考虑多个财务指标和市场因素，筛选出具有长期增长潜力和低风险的股票，并通过动态调仓和持仓管理，降低组合的波动性。此策略适用于希望在波动市场中获取稳定回报的投资者。

免责声明

本文所发布的所有内容仅供参考和技术研究，所提供的投资策略、分析和观点并不构成任何形式的投资建议。投资涉及风险，读者应根据自身的投资目标、风险承受能力及财务状况，独立做出决策。我们不对任何因文章内容而产生的投资损失或其他风险后果负责。请在投资前咨询专业的财务顾问或投资专家。
