def initialize(context):
    # 设定基准为沪深300指数
    set_benchmark('000300.XSHG')
    # 使用真实价格进行交易
    set_option('use_real_price', True)
    # 启用防未来数据机制，避免未来数据干扰策略
    set_option("avoid_future_data", True)
    # 设置固定滑点为0
    set_slippage(FixedSlippage(0.000))
    # 设置交易成本：买卖佣金各为万分之二
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0002, close_commission=0.0002, close_today_commission=0, min_commission=5), type='fund')
    # 过滤低于error级别的日志
    log.set_level('system', 'error')
    # 初始化ETF池及动量参考天数
    g.etf_pool = [
        '518880.XSHG', # 黄金ETF
        '513100.XSHG', # 纳指100
        '159915.XSHE', # 创业板100
        '510180.XSHG', # 上证180
    ]
    g.m_days = 25  # 动量参考天数
    # 每天开盘后执行交易操作
    run_daily(trade, '9:30')
