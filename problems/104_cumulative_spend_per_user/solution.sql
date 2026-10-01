WITH order_totals AS (
    SELECT o.user_id, o.order_id, o.ordered_at,
           SUM(oi.quantity * oi.unit_price) AS order_total
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'completed'
    GROUP BY o.user_id, o.order_id, o.ordered_at
)
SELECT user_id, order_id, ordered_at, order_total,
       SUM(order_total) OVER (PARTITION BY user_id ORDER BY ordered_at) AS lifetime_spend
FROM order_totals;
