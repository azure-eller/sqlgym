Finance wants a cumulative revenue chart. For each day that has at least one completed order, return the day (a DATE), that day's revenue, and the running total of revenue up to and including that day. Revenue is quantity * unit_price summed over order items. Only count orders with status 'completed'.

Return order_date, revenue, running_total, sorted by order_date.
