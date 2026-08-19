def trade(context):
    # 选择动量评分最高的ETF
    target_num = 1    
    target_list = get_rank(g.etf_pool)[:target_num]
    # 卖出当前持有的、但不在目标列表中的ETF
    hold_list = list(context.portfolio.positions)
    for etf in hold_list:
        if etf not in target_list:
            order_target_value(etf, 0)
            print(f'卖出 {etf}')
        else:
            print(f'继续持有 {etf}')
    # 买入目标ETF
    hold_list = list(context.portfolio.positions)
    if len(hold_list) < target_num:
        value = context.portfolio.available_cash / (target_num - len(hold_list))
        for etf in target_list:
            if context.portfolio.positions[etf].total_amount == 0:
                order_target_value(etf, value)
                print(f'买入 {etf}')

复制
