def get_rank(context,stock_pool):
    rank = []
    for stock in g.stock_pool:
        data = attribute_history(stock, g.momentum_day, '1d', ['close'])
        score = np.polyfit(np.arange(len(data)), data.close / data.close[0], 1)[0]
        rank.append([stock, score])
    rank.sort(key=lambda x: x[-1], reverse=True)
    log.info(data.tail(3))
    return rank[0]
