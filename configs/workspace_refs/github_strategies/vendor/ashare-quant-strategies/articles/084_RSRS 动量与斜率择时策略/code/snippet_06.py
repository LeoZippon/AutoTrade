def print_trade_info(context):
    trades = get_trades()
    for _trade in trades.values():
        print('成交记录：' + str(_trade))
    print('———————————————————————————————————————分割线————————————————————————————————————————')
