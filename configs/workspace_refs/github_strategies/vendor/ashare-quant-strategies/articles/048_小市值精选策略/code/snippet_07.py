def my_trade(context):
    codes = get_index_stocks(g.security_universe_index)  # 获取股票池中的股票
    q = query(valuation.code).filter(valuation.code.in_(codes)).order_by(valuation.circulating_market_cap.asc()).limit(100)
    codes = list(get_fundamentals(q).code)
    codes = filter_st_stock(context, codes)  # 过滤ST股票
    codes = filter_limit_stock(context, codes)  # 过滤涨停和跌停股票
    codes = filter_new_stock(context, codes)  # 过滤次新股
    codes = codes[:g.stock_num]  # 选择市值最小的前 g.stock_num 只股票
    adjust_position(context, codes, g.stock_num)  # 调整持仓

复制
