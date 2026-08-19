# 6、高股息低波动择优策略

# 1. 策略概述

该策略是一种多因子选股策略，旨在通过筛选高股息、低波动和低负债的股票，构建稳定收益的投资组合。策略通过分红、波动性和负债率等指标来筛选出优质股票，同时避免频繁调仓，提高组合稳定性。**文末获取本文源码下载方式。**

# 2. 策略逻辑

  1. **多因子选股** ：

     * 策略优先筛选出高股息率股票，然后在这些股票中进一步筛选波动性较低和负债率较低的股票，最终构建一个优质股票池。

  2. **持仓调整** ：

     * 每周根据最新的筛选结果调整持仓，卖出不再符合条件的股票，并买入新的高分股票。

  3. **风控措施** ：

     * 通过过滤涨停、跌停、ST、次新股、科创板股票等高风险股票，减少组合的不确定性和波动风险。

  4. **调仓限制** ：

     * 通过记录最近一段时间持有过的股票，避免这些股票被重新买入，从而降低频繁交易的风险。

# 3. 策略代码详细说明

## 3.1 初始化函数 (initialize)

```python
def initialize(context):
    # 设置策略的基准指数
    set_benchmark('000905.XSHG')  # 选取中证500指数作为基准
    # 使用真实价格进行交易
    set_option('use_real_price', True)
    # 防止未来数据干扰
    set_option("avoid_future_data", True)
    # 设置固定滑点为0
    set_slippage(FixedSlippage(0))
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='fund')
    # 过滤日志，仅保留error级别以上的日志
    log.set_level('order', 'error')
    # 初始化全局变量
    g.stock_num = 10  # 最大持股数量
    g.limit_days = 20  # 持仓天数限制
    g.limit_up_list = []  # 涨停股票列表
    g.hold_list = []  # 当前持仓列表
    g.history_hold_list = []  # 历史持仓列表
    g.not_buy_again_list = []  # 不再买入的股票列表
    # 每日、每周的调度任务
    run_daily(prepare_stock_list, time='9:05', reference_security='000300.XSHG')
    run_weekly(weekly_adjustment, weekday=1, time='9:30', reference_security='000300.XSHG')
    run_daily(check_limit_up, time='14:00', reference_security='000300.XSHG')
    run_daily(print_position_info, time='15:10', reference_security='000300.XSHG')
```

**功能** ：初始化策略的基本配置，包括设定基准、滑点、交易成本及每日、每周的调度任务。

## 3.2 获取股息率筛选列表 (get_dividend_ratio_filter_list)

```python
def get_dividend_ratio_filter_list(context, stock_list, sort, p1, p2):
    time1 = context.previous_date
    time0 = time1 - datetime.timedelta(days=365)
    interval = 1000
    list_len = len(stock_list)
    q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.bonus_amount_rmb
              ).filter(finance.STK_XR_XD.a_registration_date >= time0,
                       finance.STK_XR_XD.a_registration_date <= time1,
                       finance.STK_XR_XD.code.in_(stock_list[:min(list_len, interval)]))
    df = finance.run_query(q)
    if list_len > interval:
        for i in range(list_len // interval):
            q = query(finance.STK_XR_XD.code, finance.STK_XR_XD.a_registration_date, finance.STK_XR_XD.bonus_amount_rmb
                      ).filter(finance.STK_XR_XD.a_registration_date >= time0,
                               finance.STK_XR_XD.a_registration_date <= time1,
                               finance.STK_XR_XD.code.in_(stock_list[interval * (i + 1):min(list_len, interval * (i + 2))]))
            temp_df = finance.run_query(q)
            df = df.append(temp_df)
    dividend = df.fillna(0).groupby('code').sum()
    q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(dividend.index.tolist()))
    cap = get_fundamentals(q, date=time1)
    DR = pd.concat([dividend, cap.set_index('code')], axis=1, sort=False)
    DR['dividend_ratio'] = (DR['bonus_amount_rmb'] / 10000) / DR['market_cap']
    DR = DR.sort_values(by='dividend_ratio', ascending=sort)
    final_list = list(DR.index)[int(p1 * len(DR)):int(p2 * len(DR))]
    return final_list
```

**功能** ：根据最近一年分红除以当前总市值计算股息率，并筛选出指定比例的高股息股票。

## 3.3 选股模块 (get_stock_list)

```python
def get_stock_list(context):
    yesterday = context.previous_date
    initial_list = get_all_securities().index.tolist()
    initial_list = filter_kcbj_stock(initial_list)
    initial_list = filter_new_stock(context, initial_list, 375)
    initial_list = filter_st_stock(initial_list)
    dr_list = get_dividend_ratio_filter_list(context, initial_list, False, 0, 0.5)
    tv_list = get_factor_filter_list(context, dr_list, 'turnover_volatility', False, 0, 0.8)
    lev_list = get_factor_filter_list(context, tv_list, 'MLEV', True, 0, 0.5)
    q = query(valuation.code, valuation.circulating_market_cap).filter(valuation.code.in_(lev_list)).order_by(valuation.circulating_market_cap.asc())
    df = get_fundamentals(q, date=yesterday)
    final_list = list(df.code)[:15]
    return final_list
```

**功能** ：基于高股息率、低波动性和低负债率筛选股票，并进一步筛选流通市值较小的股票构建最终的股票池。

## 3.4 准备股票池 (prepare_stock_list)

```python
def prepare_stock_list(context):
    g.hold_list = [position.security for position in context.portfolio.positions.values()]
    g.history_hold_list.append(g.hold_list)
    if len(g.history_hold_list) >= g.limit_days:
        g.history_hold_list = g.history_hold_list[-g.limit_days:]
    temp_set = set(stock for hold_list in g.history_hold_list for stock in hold_list)
    g.not_buy_again_list = list(temp_set)
    if g.hold_list:
        df = get_price(g.hold_list, end_date=context.previous_date, frequency='daily', fields=['close', 'high_limit'], count=1, panel=False, fill_paused=False)
        df = df[df['close'] == df['high_limit']]
        g.high_limit_list = list(df.code)
    else:
        g.high_limit_list = []
```

**功能** ：更新当前持仓列表、最近持有过的股票列表和昨日涨停的股票列表，确保调仓时的信息准确性。

## 3.5 整体调整持仓 (weekly_adjustment)

```python
def weekly_adjustment(context):
    target_list = get_stock_list(context)
    target_list = filter_paused_stock(target_list)
    target_list = filter_limitup_stock(context, target_list)
    target_list = filter_limitdown_stock(context, target_list)
    target_list = target_list[:min(g.stock_num, len(target_list))]
    for stock in g.hold_list:
        if stock not in target_list and stock not in g.high_limit_list:
            log.info(f"卖出[{stock}]")
            close_position(context.portfolio.positions[stock])
    position_count = len(context.portfolio.positions)
    target_num = len(target_list)
    if target_num > position_count:
        value = context.portfolio.cash / (target_num - position_count)
        for stock in target_list:
            if context.portfolio.positions[stock].total_amount == 0:
                if open_position(stock, value):
                    if len(context.portfolio.positions) == target_num:
                        break
```

**功能** ：每周进行持仓调整，卖出不符合条件的股票，并买入新的高分股票。

## 3.6 涨停股监控 (check_limit_up)

```python
def check_limit_up(context):
    now_time = context.current_dt
    if g.high_limit_list:
        for stock in g
.high_limit_list:
            current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close', 'high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
            if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                log.info(f"[{stock}] 涨停打开，卖出")
                close_position(context.portfolio.positions[stock])
```

**功能** ：监控昨日涨停的股票，如果涨停打开且不在买入列表中，则卖出该股票。

## 3.7 交易模块 (order_target_value_, open_position, close_position)

```python
def order_target_value_(security, value):
    log.debug(f"Order {security} to value {value}" if value != 0 else f"Selling out {security}")
    return order_target_value(security, value)
def open_position(security, value):
    order = order_target_value_(security, value)
    return order is not None and order.filled > 0
def close_position(position):
    order = order_target_value_(position.security, 0)
    return order is not None and order.status == OrderStatus.held and order.filled == order.amount
```

**功能** ：提供统一的开仓、平仓和下单操作函数，保证交易逻辑的一致性。

## 3.8 打印每日持仓信息 (print_position_info)

```python
def print_position_info(context):
    trades = get_trades()
    for _trade in trades.values():
        print(f'成交记录：{_trade}')
    for position in context.portfolio.positions.values():
        securities = position.security
        cost = position.avg_cost
        price = position.price
        ret = 100 * (price / cost - 1)
        value = position.value
        amount = position.total_amount
        print(f'代码: {securities}')
        print(f'成本价: {cost:.2f}')
        print(f'现价: {price}')
        print(f'收益率: {ret:.2f}%')
        print(f'持仓(股): {amount}')
        print(f'市值: {value:.2f}')
        print('———————————————————————————————————')
    print('———————————————————————————————————————分割线————————————————————————————————————————')
```

**功能** ：打印每日持仓信息和当日交易记录，方便跟踪和分析策略表现。

# 4. 策略总结

**“高股息低波动择优策略”** 是一个结合了股息率、波动性和负债率等多因子筛选的策略。通过定期调仓与严格的筛选条件，确保组合的稳定性与优质性，适合追求稳定收益和长期价值投资的投资者。

## 高股息低波动择优策略完整源码

下载链接: <https://pan.baidu.com/s/1qtWy8H1k-khIYApTMWGdIg>

提取码: 5gru

免责声明

本文所发布的所有内容仅供参考和技术研究，所提供的投资策略、分析和观点并不构成任何形式的投资建议。投资涉及风险，读者应根据自身的投资目标、风险承受能力及财务状况，独立做出决策。我们不对任何因文章内容而产生的投资损失或其他风险后果负责。请在投资前咨询专业的财务顾问或投资专家。
