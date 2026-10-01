For each user with at least one completed order, show when they first and last bought something and how much those orders were for. An order's total is the sum of quantity * unit_price over its items. Only count orders with status 'completed'. If a user has only one order, it is both their first and last.

Return user_id, first_order_at, first_order_total, last_order_at, last_order_total.
