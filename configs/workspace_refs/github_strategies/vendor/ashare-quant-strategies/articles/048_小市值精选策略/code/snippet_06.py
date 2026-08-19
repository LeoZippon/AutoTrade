def process_initialize(context):
    log.info('运行 process_initialize')
    g.security_universe_index = "399101.XSHE"  # 股票池基准指数：中小板指数
    g.stock_num = 5  # 每次持有的最大股票数量
    run_daily(my_trade, time='09:40')  # 每天9:40进行交易操作

复制
