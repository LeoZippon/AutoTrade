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
