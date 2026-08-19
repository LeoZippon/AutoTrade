def check_limit_up(context):
    now_time = context.current_dt
    if g.high_limit_list:
        for stock in g
.high_limit_list:
            current_data = get_price(stock, end_date=now_time, frequency='1m', fields=['close', 'high_limit'], skip_paused=False, fq='pre', count=1, panel=False, fill_paused=True)
            if current_data.iloc[0, 0] < current_data.iloc[0, 1]:
                log.info(f"[{stock}] 涨停打开，卖出")
                close_position(context.portfolio.positions[stock])

复制
