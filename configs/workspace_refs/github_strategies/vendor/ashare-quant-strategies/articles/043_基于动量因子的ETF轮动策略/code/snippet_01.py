def initialize(context):
    set_benchmark('000300.XSHG')  # 设定沪深300指数为基准
    set_option('use_real_price', True)  # 使用实时价格进行交易
    set_option("avoid_future_data", True)  # 避免未来函数
    set_slippage(FixedSlippage(0.000))  # 设置滑点为零，假设无滑点影响
    set_order_cost(OrderCost(open_tax=0, close_tax=0, open_commission=0.0002, close_commission=0.0002, close_today_commission=0, min_commission=5), type='fund')
    log.set_level('system', 'error')  # 过滤系统级别的日志
    # 定义ETF池
    g.etf_pool = [
        '161725.XSHE', # 白酒ETF
        '159992.XSHE', # 创新药ETF
        '560080.XSHG', # 中药ETF
        '515700.XSHG', # 新能源车ETF
        '515250.XSHG', # 智能汽车ETF
        '515790.XSHG', # 光伏ETF
        '515880.XSHG', # 通信ETF
        '159819.XSHE', # 人工智能ETF
        '512720.XSHG', # 计算机ETF
        '159740.XSHE', # 恒生科技ETF
        '159985.XSHE', # 豆粕ETF
        '162411.XSHE', # 华宝油气ETF
        '518880.XSHG', # 黄金ETF
        '513100.XSHG', # 纳指100ETF
    ]
    g.m_days = 25  # 动量参考的天数
    run_daily(trade, '9:40')  # 每天运行确保即时捕捉动量变化
