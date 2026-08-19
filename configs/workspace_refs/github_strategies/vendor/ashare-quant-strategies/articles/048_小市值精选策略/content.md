# 48、小市值精选策略

# 1. 策略概述

**小市值精选策略** 是一种基于市值排序的股票筛选和交易策略。策略主要通过选择市值较小的股票进行投资，以期获得超额收益。此策略会每日检查股票池中的股票，筛选出符合条件的前若干只股票，并进行调整持仓，确保投资组合中持有的股票符合小市值和其他筛选条件。

# 2. 策略各部分功能代码详细技术文档说明

## 2.1 策略初始化 (process_initialize)

策略初始化时，设置股票池的基准指数和每次持有的最大股票数量。在实际交易中，策略会每日进行交易操作，并在指定的时间点执行交易逻辑。

```python
def process_initialize(context):
    log.info('运行 process_initialize')
    g.security_universe_index = "399101.XSHE"  # 股票池基准指数：中小板指数
    g.stock_num = 5  # 每次持有的最大股票数量
    run_daily(my_trade, time='09:40')  # 每天9:40进行交易操作
```

## 2.2 每日交易逻辑 (my_trade)

策略的核心交易逻辑。每日开盘时获取股票池中的股票，按照流通市值从小到大排序，选择符合条件的前 g.stock_num 只股票进行投资，并调整持仓。

```python
def my_trade(context):
    codes = get_index_stocks(g.security_universe_index)  # 获取股票池中的股票
    q = query(valuation.code).filter(valuation.code.in_(codes)).order_by(valuation.circulating_market_cap.asc()).limit(100)
    codes = list(get_fundamentals(q).code)
    codes = filter_st_stock(context, codes)  # 过滤ST股票
    codes = filter_limit_stock(context, codes)  # 过滤涨停和跌停股票
    codes = filter_new_stock(context, codes)  # 过滤次新股
    codes = codes[:g.stock_num]  # 选择市值最小的前 g.stock_num 只股票
    adjust_position(context, codes, g.stock_num)  # 调整持仓
```

## 2.3 持仓调整 (adjust_position)

根据筛选后的股票列表调整当前持仓。策略会卖出不符合条件的持仓股票，并买入新选中的股票，确保投资组合中持有的是最优的股票组合。

```python
def adjust_position(context, buy_stocks, stock_num):
    position_codes = list(context.portfolio.positions.keys())
    for stock in position_codes:
        if stock not in buy_stocks:
            log.info("stock [%s] in position is not buyable" % (stock))
            position = context.portfolio.positions[stock]
            order_target(stock, 0)  # 卖出不再符合条件的股票
        else:
            log.info("stock [%s] is already in position" % (stock))
    position_count = len(context.portfolio.positions)
    if stock_num > position_count:
        value = context.portfolio.cash / (stock_num - position_count)
        for stock in buy_stocks:
            if stock not in context.portfolio.positions.keys():
                order_target_value(stock, value)  # 买入新选中的股票
                if len(context.portfolio.positions) == stock_num:
                    break
```

## 2.4 过滤函数

多个过滤函数用于筛选掉不符合条件的股票，包括停牌、ST股、涨跌停、次新股等，确保最终选出的股票符合预期的投资标准。

```python
# 过滤停牌股票
def filter_paused_stock(stock_list):
    current_data = get_current_data()
    return [stock for stock in stock_list if not current_data[stock].paused]
# 过滤ST股票
def filter_st_stock(context, stock_list):
    st_data = get_extras('is_st', stock_list, end_date=context.current_dt, count=1).iloc[0]
    return st_data[st_data == False].index.tolist()
# 过滤涨停和跌停的股票
def filter_limit_stock(context, stock_list):
    pdata = get_price(stock_list, count=1, frequency='1m', end_date=context.current_dt, fields=['close','high_limit','low_limit'], panel=False)
    return pdata[(pdata.high_limit > pdata.close) & (pdata.low_limit < pdata.close)].code.tolist()
# 过滤次新股
def filter_new_stock(context, stock_list):
    sdata = get_all_securities()
    sdata.start_date = pd.to_datetime(sdata.start_date).dt.date
    sdata = sdata.loc[stock_list]
    return sdata[(sdata.start_date - context.current_dt.date()) <= datetime.timedelta(days=250)].index.tolist()
```

## 2.5 交易检查 (check_class)

策略提供了一个函数用于调试和检查交易状态，包括账户信息、持仓情况、订单信息等，帮助用户了解策略运行的内部情况。

```python
def check_class(context):
    log.info("------------------以下为portfolio对象-------------------")
    log.info([context.portfolio.total_value, context.portfolio.available_cash, context.portfolio.locked_cash])
    log.info("------------------以下为position对象-------------------")
    position = context.portfolio.positions['000001.XSHE']
    log.info([position.security, position.total_amount, position.closeable_amount, position.avg_cost, position.acc_avg_cost, position.side, position.price, position.value])
    log.info("------------------以下为order对象-------------------")
    o = list(get_orders().values())
    if o:
        log.info(o[0])
```

# 3. 优化建议

  1. **增加多样化筛选条件** ：除了市值筛选外，可以增加其他基本面或技术面的筛选条件，如市盈率、收益增长率等，以提高选股的准确性。

  2. **动态调仓机制** ：根据市场变化动态调整持仓比例和持仓数量，增强策略的灵活性。

  3. **风险控制** ：加入止损和止盈机制，避免市场极端行情对投资组合的冲击。

4\. 总结

**小市值精选策略** 通过严格的筛选和持仓调整机制，力求在小市值股票中捕捉超额收益的机会。策略通过每日检查和筛选股票池，及时调整持仓，确保组合中持有的股票符合最优条件，适合在一定市场环境下获取稳健收益。

免责声明

本文所发布的所有内容仅供参考和技术研究，所提供的投资策略、分析和观点并不构成任何形式的投资建议。投资涉及风险，读者应根据自身的投资目标、风险承受能力及财务状况，独立做出决策。我们不对任何因文章内容而产生的投资损失或其他风险后果负责。请在投资前咨询专业的财务顾问或投资专家。
