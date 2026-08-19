def initialize(context):
    # 设定基准
    set_benchmark('000905.XSHG')
    # 用真实价格交易
    set_option('use_real_price', True)
    # 打开防未来函数
    set_option("avoid_future_data", True)
    # 将滑点设置为0
    set_slippage(FixedSlippage(0))
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='fund')
    # 过滤order中低于error级别的日志
    log.set_level('order', 'error')
    # 初始化全局变量
    g.stock_num = 10  # 持股数量
    g.limit_days = 20  # 持有天数
    g.limit_up_list = []  # 涨停股票列表
    g.hold_list = []  # 持仓股票列表
    g.history_hold_list = []  # 历史持仓股票列表
    g.not_buy_again_list = []  # 禁止再买入的股票列表
    # 设置交易时间，每天运行
    run_daily(prepare_stock_list, time='9:05', reference_security='000300.XSHG')
    run_weekly(weekly_adjustment, weekday=1, time='9:40', reference_security='000300.XSHG')
    run_daily(check_limit_up, time='14:00', reference_security='000300.XSHG')
    run_daily(print_position_info, time='15:10', reference_security='000300.XSHG')

复制
