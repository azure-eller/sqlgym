WITH gaps AS (
    SELECT user_id,
           ordered_at::DATE - LAG(ordered_at::DATE) OVER (PARTITION BY user_id ORDER BY ordered_at) AS gap_days
    FROM orders
    WHERE status = 'completed'
)
SELECT user_id, COUNT(*) AS completed_orders, AVG(gap_days) AS avg_days_between
FROM gaps
GROUP BY user_id
HAVING COUNT(*) >= 2;
