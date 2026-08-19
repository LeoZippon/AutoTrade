def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_slippage(FixedSlippage(0.001))
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='fund')
    log.set_level('order', 'error')
    # 选股池设置
    g.stock_pool = [
        '510050.XSHG',  # 上证50ETF
        '159928.XSHE',  # 中证消费ETF
        '510300.XSHG',  # 沪深300ETF
        '159949.XSHE',  # 创业板50ETF
    ]
    g.stock_num = 1  # 持仓股票数
    g.momentum_day = 20  # 动量计算的天数
    g.ref_stock = '000300.XSHG'  # 择时基础数据使用沪深300指数
    g.N = 18  # 计算斜率的天数
    g.M = 600  # 计算标准分zscore的天数
    g.score_threshold = 0.7  # RSRS标准分的阈值
    g.mean_day = 30  # 计算均线的天数
    g.mean_diff_day = 2  # 均线的差异天数
    # 初始化斜率序列
    g.slope_series = initial_slope_series()[:-1]  # 除去第一天，避免重复
    run_daily(my_trade, time='9:30', reference_security='000300.XSHG')
    run_daily(check_lose, time='open', reference_security='000300.XSHG')
    run_daily(print_trade_info, time='15:30', reference_security='000300.XSHG')

复制
