def order_target_value_(security, value):
    log.debug(f"Order {security} to value {value}" if value != 0 else f"Selling out {security}")
    return order_target_value(security, value)
def open_position(security, value):
    order = order_target_value_(security, value)
    return order is not None and order.filled > 0
def close_position(position):
    order = order_target_value_(position.security, 0)
    return order is not None and order.status == OrderStatus.held and order.filled == order.amount
