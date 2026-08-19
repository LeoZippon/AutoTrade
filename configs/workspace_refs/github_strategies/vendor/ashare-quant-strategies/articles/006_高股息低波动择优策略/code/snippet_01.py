def initialize(context):
    # 设置策略的基准指数
    set_benchmark('000905.XSHG')  # 选取中证500指数作为基准
    # 使用真实价格进行交易
    set_option('use_real_price', True)
    # 防止未来数据干扰
    set_option("avoid_future_data", True)
    # 设置固定滑点为0
    set_slippage(FixedSlippage(0))
    # 设置交易成本
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, close_today_commission=0, min_commission=5), type='fund')
    # 过滤日志，仅保留error级别以上的日志
    log.set_level('order', 'error')
    # 初始化全局变量
    g.stock_num = 10  # 最大持股数量
    g.limit_days = 20  # 持仓天数限制
    g.limit_up_list = []  # 涨停股票列表
    g.hold_list = []  # 当前持仓列表
    g.history_hold_list = []  # 历史持仓列表
    g.not_buy_again_list = []  # 不再买入的股票列表
    # 每日、每周的调度任务
    run_daily(prepare_stock_list, time='9:05', reference_security='000300.XSHG')
    run_weekly(weekly_adjustment, weekday=1, time='9:30', reference_security='000300.XSHG')
    run_daily(check_limit_up, time='14:00', reference_security='000300.XSHG')
    run_daily(print_position_info, time='15:10', reference_security='000300.XSHG')
