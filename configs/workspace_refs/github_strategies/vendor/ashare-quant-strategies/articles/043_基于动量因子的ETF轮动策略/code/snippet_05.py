def get_rank(etf_pool):
    score_list = []
    for etf in etf_pool:
        df = attribute_history(etf, g.m_days, '1d', ['close'])
        y = df['log'] = np.log(df.close)  # 计算对数收益率
        x = df['num'] = np.arange(df.log.size)  # 创建等差数列用于回归
        slope, intercept = np.polyfit(x, y, 1)  # 线性回归，计算斜率和截距
        annualized_returns = np.exp(slope * 250) - 1  # 计算年化收益率
        r_squared = 1 - sum((y - (slope * x + intercept))**2) / ((len(y) - 1) * np.var(y))  # 计算R²判定系数
        score = annualized_returns * r_squared  # 动量评分
        score_list.append(score)
    # 将得分存储在DataFrame中并排序
    df = pd.DataFrame(index=etf_pool, data={'score': score_list})
    df = df.sort_values(by='score', ascending=False)
    # 记录ETF得分
    for etf in df.index:
        record(**{etf: round(df.loc[etf, 'score'], 2)})
    return list(df.index)

复制
