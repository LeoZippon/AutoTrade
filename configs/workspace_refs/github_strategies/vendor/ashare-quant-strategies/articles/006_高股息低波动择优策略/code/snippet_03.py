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
