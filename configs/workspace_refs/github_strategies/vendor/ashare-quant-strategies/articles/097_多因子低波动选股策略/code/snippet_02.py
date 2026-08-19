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
