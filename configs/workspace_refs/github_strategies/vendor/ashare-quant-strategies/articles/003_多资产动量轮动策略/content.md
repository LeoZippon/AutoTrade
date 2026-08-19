# 3、多资产动量轮动策略

# 1. 策略概述

该策略基于动量因子，进行多资产类别的ETF轮动投资。通过计算不同ETF的动量得分，选择动量最高的ETF进行投资，其他ETF则被清仓。策略运行频率为每日，确保及时捕捉市场中的动量变化。

# 2. 策略逻辑

  1. **动量因子计算** ：

     * 使用回归分析计算每个ETF的年化收益率和判定系数（R²），并将其乘积作为动量得分。

     * 年化收益率表示价格趋势的强度，判定系数则反映趋势的稳定性。

  2. **ETF筛选与轮动** ：

     * 每天开盘后，选择动量得分最高的ETF进行投资，其余ETF则被卖出。

     * 策略仅持有动量得分最高的一个ETF。

  3. **风控措施** ：

     * 通过严格的筛选和轮动机制，策略力求在不同市场环境中维持较高的收益潜力，并规避低动量资产的持仓风险。

# 3. 策略代码详细说明

## 3.1 初始化函数 (initialize)

```python
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
```

**功能** ：初始化策略的基本参数，包括设定基准、滑点、交易成本，以及动量因子的计算周期。设置每日的交易任务以确保策略的及时性。

## 3.2 动量因子计算与ETF排序 (get_rank)

```python
def get_rank(etf_pool):
    score_list = []
    for etf in etf_pool:
        # 获取指定ETF的收盘价历史数据
        df = attribute_history(etf, g.m_days, '1d', ['close'])
        # 计算对数收益率
        y = df['log'] = np.log(df.close)
        x = df['num'] = np.arange(df.log.size)
        # 回归分析，计算斜率（slope）和截距（intercept）
        slope, intercept = np.polyfit(x, y, 1)
        # 计算年化收益率
        annualized_returns = np.exp(slope * 250) - 1
        # 计算判定系数R²
        r_squared = 1 - (sum((y - (slope * x + intercept))**2) / ((len(y) - 1) * np.var(y, ddof=1)))
        # 计算动量得分
        score = annualized_returns * r_squared
        score_list.append(score)
    # 将动量得分与ETF对应，按得分降序排列
    df = pd.DataFrame(index=etf_pool, data={'score': score_list})
    df = df.sort_values(by='score', ascending=False)
    # 打印每个ETF的得分用于记录
    record(黄金=round(df.loc['518880.XSHG', 'score'], 2))
    record(纳指=round(df.loc['513100.XSHG', 'score'], 2))
    record(成长=round(df.loc['159915.XSHE', 'score'], 2))
    record(价值=round(df.loc['510180.XSHG', 'score'], 2))
    return list(df.index)
```

**功能** ：计算每个ETF的动量得分，并按得分从高到低排序，返回排序后的ETF列表。得分结合了年化收益率与R²，综合考虑了趋势强度与稳定性。

## 3.3 交易逻辑 (trade)

```python
def trade(context):
    # 获取动量得分最高的ETF
    target_list = get_rank(g.etf_pool)[:1]  # 仅选择一个动量最高的ETF
    # 卖出不在目标列表中的ETF
    hold_list = list(context.portfolio.positions)
    for etf in hold_list:
        if etf not in target_list:
            order_target_value(etf, 0)
            print(f'卖出 {etf}')
        else:
            print(f'继续持有 {etf}')
    # 如果有空余资金且目标ETF未持仓，则买入
    hold_list = list(context.portfolio.positions)
    if len(hold_list) < len(target_list):
        value = context.portfolio.available_cash / (len(target_list) - len(hold_list))
        for etf in target_list:
            if context.portfolio.positions[etf].total_amount == 0:
                order_target_value(etf, value)
                print(f'买入 {etf}')
```

**功能** ：执行交易逻辑。策略每天检查持仓，卖出不符合条件的ETF，买入动量得分最高的ETF，确保组合中始终持有表现最强的资产。

# 4. 策略总结

**"多资产动量轮动策略"** 通过动量因子轮动不同类别的ETF，实现不同资产之间的动态配置。策略主要特点是：

  * **动量因子** ：基于年化收益率和判定系数R²计算动量得分。

  * **资产轮动** ：策略每日检查资产动量，始终持有动量最强的资产类别。

  * **多样性与稳健性** ：通过不同类别的ETF（如黄金、海外资产、成长股、价值股）分散投资风险，捕捉各类市场机会。

该策略适合希望通过ETF实现资产轮动，并在不同市场环境中获取稳健收益的投资者。

免责声明

本文所发布的所有内容仅供参考和技术研究，所提供的投资策略、分析和观点并不构成任何形式的投资建议。投资涉及风险，读者应根据自身的投资目标、风险承受能力及财务状况，独立做出决策。我们不对任何因文章内容而产生的投资损失或其他风险后果负责。请在投资前咨询专业的财务顾问或投资专家。
