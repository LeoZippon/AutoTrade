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
