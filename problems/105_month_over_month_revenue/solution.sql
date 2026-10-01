WITH monthly AS (
    SELECT date_trunc('month', o.ordered_at)::DATE AS month,
           SUM(oi.quantity * oi.unit_price) AS revenue
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'completed'
    GROUP BY 1
),
with_prev AS (
    SELECT month, revenue, LAG(revenue) OVER (ORDER BY month) AS prev_revenue
    FROM monthly
)
SELECT month, revenue, prev_revenue,
       100.0 * (revenue - prev_revenue) / prev_revenue AS pct_change
FROM with_prev
ORDER BY month;
