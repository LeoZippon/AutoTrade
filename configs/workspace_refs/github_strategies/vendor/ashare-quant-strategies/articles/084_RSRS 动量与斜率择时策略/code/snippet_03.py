def get_timing_signal(context, stock):
    g.mean_diff_day = 5
    close_data = attribute_history(g.ref_stock, g.mean_day + g.mean_diff_day, '1d', ['close'])
    high_low_data = attribute_history(g.ref_stock, g.N, '1d', ['high', 'low'])
    intercept, slope, r2 = get_ols(high_low_data.low, high_low_data.high)
    g.slope_series.append(slope)
    rsrs_score = get_zscore(g.slope_series[-g.M:]) * r2
    if rsrs_score > g.score_threshold: return "BUY"
    elif rsrs_score < -g.score_threshold: return "SELL"
    else: return "KEEP"
