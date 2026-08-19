def trade(context):
    # 获取动量得分最高的ETF
    target_list = get_rank(g.etf_pool)[:1]  # 仅选择一个动量最高的ETF
    # 卖出不在目标列表中的ETF
    hold_list = list(context.portfolio.positions)
    for etf in hold_list:
        if etf not in target_list:
            order_target_value(etf, 0)
            print(f'卖出 {etf}')
        else:
            print(f'继续持有 {etf}')
    # 如果有空余资金且目标ETF未持仓，则买入
    hold_list = list(context.portfolio.positions)
    if len(hold_list) < len(target_list):
        value = context.portfolio.available_cash / (len(target_list) - len(hold_list))
        for etf in target_list:
            if context.portfolio.positions[etf].total_amount == 0:
                order_target_value(etf, value)
                print(f'买入 {etf}')
