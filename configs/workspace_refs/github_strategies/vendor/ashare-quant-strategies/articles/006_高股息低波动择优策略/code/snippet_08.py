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
