WITH order_totals AS (
    SELECT o.order_id, o.user_id, o.ordered_at,
           SUM(oi.quantity * oi.unit_price) AS order_total
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'completed'
    GROUP BY o.order_id, o.user_id, o.ordered_at
),
ranked AS (
    SELECT *,
           date_trunc('month', ordered_at)::DATE AS month,
           RANK() OVER (PARTITION BY date_trunc('month', ordered_at) ORDER BY order_total DESC) AS rnk
    FROM order_totals
)
SELECT month, order_id, user_id, order_total
FROM ranked
WHERE rnk = 1;
