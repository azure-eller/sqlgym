WITH order_totals AS (
    SELECT o.user_id, o.order_id, o.ordered_at,
           SUM(oi.quantity * oi.unit_price) AS order_total
    FROM orders o
    JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.status = 'completed'
    GROUP BY o.user_id, o.order_id, o.ordered_at
),
numbered AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY ordered_at) AS from_first,
           ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY ordered_at DESC) AS from_last
    FROM order_totals
)
SELECT f.user_id,
       f.ordered_at AS first_order_at, f.order_total AS first_order_total,
       l.ordered_at AS last_order_at, l.order_total AS last_order_total
FROM numbered f
JOIN numbered l ON l.user_id = f.user_id AND l.from_last = 1
WHERE f.from_first = 1;
