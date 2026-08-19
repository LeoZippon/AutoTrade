def my_trade(context):
    hour = context.current_dt.hour
    minute = context.current_dt.minute
    if hour == 9 and minute == 30:
        check_out_list = get_rank(context, g.stock_pool)
        timing_signal = get_timing_signal(context, g.ref_stock)
        print('今日自选及择时信号:{} {}'.format(check_out_list, timing_signal))
        if timing_signal == 'SELL':
            for stock in context.portfolio.positions:
                position = context.portfolio.positions[stock]
                close_position(position)
        elif timing_signal == 'BUY' or timing_signal == 'KEEP':
            adjust_position(context, check_out_list)
        else: pass
