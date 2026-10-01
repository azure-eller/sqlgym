For every completed order, show how much the user has spent in total up to and including that order (their lifetime spend at that point, counting their orders in time order). An order's total is the sum of quantity * unit_price over its items. Only count orders with status 'completed'.

Return user_id, order_id, ordered_at, order_total, lifetime_spend.
