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

复制
