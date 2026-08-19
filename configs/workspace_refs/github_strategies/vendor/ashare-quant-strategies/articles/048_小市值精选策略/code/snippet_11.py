def check_class(context):
    log.info("------------------以下为portfolio对象-------------------")
    log.info([context.portfolio.total_value, context.portfolio.available_cash, context.portfolio.locked_cash])
    log.info("------------------以下为position对象-------------------")
    position = context.portfolio.positions['000001.XSHE']
    log.info([position.security, position.total_amount, position.closeable_amount, position.avg_cost, position.acc_avg_cost, position.side, position.price, position.value])
    log.info("------------------以下为order对象-------------------")
    o = list(get_orders().values())
    if o:
        log.info(o[0])

复制
