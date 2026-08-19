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

复制
