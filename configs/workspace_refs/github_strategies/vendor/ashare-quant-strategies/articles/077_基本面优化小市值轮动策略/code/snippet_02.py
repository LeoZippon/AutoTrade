from jqdata import *
import numpy as np
import pandas as pd
import talib
import datetime
## 初始化函数，设定要操作的股票、基准等等
def initialize(context):
    # 设定基准为沪深300
    set_benchmark('000300.XSHG')
    # 设定滑点
    set_slippage(FixedSlippage(0.01))
    # 开启动态复权模式，使用真实价格交易
    set_option('use_real_price', True)
    # 设置成交量比例
    set_option('order_volume_ratio', 1)
    # 设置交易费用
    set_order_cost(OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5), type='stock')
    # 初始化全局变量和容器
    check_container_initialize()
    check_dynamic_initialize()
    check_stocks_initialize()
    sell_initialize()
    buy_initialize()
    # 关闭提示信息
    log.set_level('order', 'info')
    # 设置定时任务
    run_daily(check_stocks, '9:15')  # 选股
    run_daily(main_stock_pick, '9:16')  # 生成买卖列表
    run_daily(sell_every_day, 'open')  # 卖出未成功卖出的股票
    run_daily(trade, 'open')  # 交易
    run_daily(selled_security_list_count, 'after_close')  # 统计卖出日期计数
## 动态仓位、频率、计数初始化函数
def check_dynamic_initialize():
    g.security_max_proportion = 1  # 个股最大持仓比重
    g.check_stocks_refresh_rate = 1  # 选股和买卖频率
    g.max_hold_stocknum = 7  # 最大持仓数量
    g.buy_refresh_rate = 20  # 买入频率
    g.sell_refresh_rate = 10  # 卖出频率
    g.check_stocks_days = 0  # 选股频率计数器
    g.days = 0  # 机器学习选股频率计数器
    g.buy_trade_days = 0  # 买卖交易频率计数器
    g.sell_trade_days = 0
## 股票池初筛设置函数
def check_stocks_initialize():
    g.filter_paused = True  # 过滤停盘
    g.filter_delisted = True  # 过滤退市
    g.only_st = False  # 只保留ST股票
    g.filter_st = True  # 过滤ST股票
    g.security_universe_index = ['all_a_securities']  # 股票池
    g.security_universe_user_securities = []  # 用户自定义股票池
    g.industry_list = []  # 行业列表
    g.concept_list = []  # 概念列表
    g.blacklist = ['300268.XSHE', '600035.XSHG', '300028.XSHE']  # 黑名单
## 主选股函数
def main_stock_pick(context):
    if g.days % g.check_stocks_refresh_rate != 0:
        g.days += 1
        return
    g.sell_stock_list = []
    g.buy_stock_list = []
    # 小市值轮动策略 - 基本面优化版
    q = query(valuation.code).filter(
        indicator.inc_revenue_annual > 0,
        indicator.inc_revenue_year_on_year > 20,
        indicator.inc_net_profit_to_shareholders_year_on_year > 0,
        indicator.inc_net_profit_to_shareholders_annual > 40,
        valuation.code.in_(g.check_out_lists)
    ).order_by(valuation.market_cap.asc())
    df = get_fundamentals(q)
    stockset = list(df['code'])
    g.sell_stock_list1 = list(context.portfolio.positions.keys())
    current_data = get_current_data()
    paused_list = [stock for stock in g.sell_stock_list1 if current_data[stock].paused]
    for stock in g.sell_stock_list1:
        buy_time = context.portfolio.positions[stock].init_time
        current_time = pd.Timestamp(context.current_dt.date())
        d_count = current_time - pd.Timestamp(buy_time)
        df_cost = get_price(stock, count=d_count.days + 2, end_date=buy_time, frequency='daily', fields=['high'])
        cost = df_cost['high'].max()
        price = context.portfolio.positions[stock].price
        YL = (price - cost) / cost
        if stock in paused_list:
            continue
        elif (stock not in stockset[:g.max_hold_stocknum]) or (YL < -0.14):
            g.sell_stock_list.append(stock)
    for stock in stockset[:g.max_hold_stocknum]:
        if stock not in g.sell_stock_list:
            g.buy_stock_list.append(stock)
    g.days = 1
    return g.sell_stock_list, g.buy_stock_list
## 容器初始化
def check_container_initialize():
    g.sell_stock_list = []
    g.buy_stock_list = []
    g.open_sell_securities = []
    g.selled_security_list = {}
## 出场初始化
def sell_initialize():
    g.sell_will_buy = True  # 是否卖出 buy_lists 中的股票
    g.sell_by_amount = None
    g.sell_by_percent = None
## 入场初始化
def buy_initialize():
    g.filter_holded = False  # 是否可重复买入
    g.order_style_str = 'by_cap_mean'  # 委托类型
    g.order_style_value = 100
## 股票初筛
def check_stocks(context):
    if g.check_stocks_days % g.check_stocks_refresh_rate != 0:
        g.check_stocks_days += 1
        return
    g.check_out_lists = get_security_universe(context, g.security_universe_index, g.security_universe_user_securities)
    g.check_out_lists = industry_filter(context, g.check_out_lists, g.industry_list)
    g.check_out_lists = concept_filter(context, g.check_out_lists, g.concept_list)
    g.check_out_lists = st_filter(context, g.check_out_lists)
    g.check_out_lists = paused_filter(context, g.check_out_lists)
    g.check_out_lists = delisted_filter(context, g.check_out_lists)
    g.check_out_lists = [s for s in g.check_out_lists if s not in g.blacklist]
    g.check_stocks_days = 1
## 卖出未卖出成功的股票
def sell_every_day(context):
    g.open_sell_securities = list(set(g.open_sell_securities))
    open_sell_securities = [s for s in context.portfolio.positions.keys() if s in g.open_sell_securities]
    for stock in open_sell_securities:
        order_target_value(stock, 0)
    g.open_sell_securities = [s for s in g.open_sell_securities if s in context.portfolio.positions.keys()]
## 交易函数
def trade(context):
    buy_lists = g.buy_stock_list
    if g.buy_trade_days % g.buy_refresh_rate == 0:
        buy_lists = high_limit_filter(context, buy_lists)
        log.info('最终购买列表:', buy_lists)
    if g.sell_trade_days % g.sell_refresh_rate == 0:
        sell(context, buy_lists)
        g.sell_trade_days = 1
    else:
        g.sell_trade_days += 1
    if g.buy_trade_days % g.buy_refresh_rate == 0:
        buy(context, buy_lists)
        g.buy_trade_days = 1
    else:
        g.buy_trade_days += 1
# 交易函数 - 出场
def sell(context, buy_lists):
    init_sl = context.portfolio.positions.keys()
    sell_lists = context.portfolio.positions.keys()
    if not g.sell_will_buy:
        sell_lists = [security for security in sell_lists if security not in buy_lists]
    sell_lists = g.sell_stock_list
    for stock in sell_lists:
        sell_by_amount_or_percent_or_none(context, stock, g.sell_by_amount, g.sell_by_percent, g.open_sell_securities)
    selled_security_list_dict(context, init_sl)
# 交易函数 - 入场
def buy(context, buy_lists):
    buy_lists = holded_filter(context, buy_lists)
    Num = g.max_hold_stocknum - len(context.portfolio.positions)
    buy_lists = buy_lists[:Num]
    if buy_lists:
        result = order_style(context, buy_lists, g.max_hold_stocknum, g.order_style_str, g.order_style_value)
        for stock in buy_lists:
            if len(context.portfolio.positions) < g.max_hold_stocknum:
                Cash = result[stock]
                value = judge_security_max_proportion(context, stock, Cash, g.security_max_proportion)
                amount =
 max_buy_value_or_amount(stock, value, None, None)
                order(stock, amount, MarketOrderStyle())
## 过滤停牌股票
def paused_filter(context, security_list):
    if g.filter_paused:
        current_data = get_current_data()
        security_list = [stock for stock in security_list if not current_data[stock].paused]
    return security_list
## 过滤退市股票
def delisted_filter(context, security_list):
    if g.filter_delisted:
        current_data = get_current_data()
        security_list = [stock for stock in security_list if not (('退' in current_data[stock].name) or ('*' in current_data[stock].name))]
    return security_list
## 过滤ST股票
def st_filter(context, security_list):
    if g.only_st:
        current_data = get_current_data()
        security_list = [stock for stock in security_list if current_data[stock].is_st]
    else:
        if g.filter_st:
            current_data = get_current_data()
            security_list = [stock for stock in security_list if not current_data[stock].is_st]
    return security_list
## 过滤涨停股票
def high_limit_filter(context, security_list):
    current_data = get_current_data()
    security_list = [stock for stock in security_list if not (current_data[stock].day_open >= current_data[stock].high_limit)]
    return security_list
## 获取股票池
def get_security_universe(context, security_universe_index, security_universe_user_securities):
    temp_index = []
    for s in security_universe_index:
        if s == 'all_a_securities':
            temp_index += list(get_all_securities(['stock'], context.current_dt.date()).index)
        else:
            temp_index += get_index_stocks(s)
    for x in security_universe_user_securities:
        temp_index += x
    return sorted(list(set(temp_index)))
## 行业过滤
def industry_filter(context, security_list, industry_list):
    if not industry_list:
        return security_list
    else:
        securities = []
        for s in industry_list:
            temp_securities = get_industry_stocks(s)
            securities += temp_securities
        security_list = [stock for stock in security_list if stock in securities]
        return security_list
## 概念过滤
def concept_filter(context, security_list, concept_list):
    if not concept_list:
        return security_list
    else:
        securities = []
        for s in concept_list:
            temp_securities = get_concept_stocks(s)
            securities += temp_securities
        security_list = [stock for stock in security_list if stock in securities]
        return security_list
## 卖出股票日期计数
def selled_security_list_count(context):
    if g.selled_security_list:
        for stock in g.selled_security_list.keys():
            g.selled_security_list[stock] += 1
## 判断是否可重复买入
def holded_filter(context, security_list):
    if not g.filter_holded:
        security_list = [stock for stock in security_list if stock not in context.portfolio.positions.keys()]
    return security_list
## 卖出股票加入字典
def selled_security_list_dict(context, security_list):
    selled_sl = [s for s in security_list if s not in context.portfolio.positions.keys()]
    if selled_sl:
        for stock in selled_sl:
            g.selled_security_list[stock] = 0

复制
