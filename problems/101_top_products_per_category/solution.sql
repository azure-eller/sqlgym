WITH product_revenue AS (
    SELECT oi.category, oi.product, SUM(oi.quantity * oi.unit_price) AS revenue
    FROM order_items oi
    JOIN orders o ON o.order_id = oi.order_id
    WHERE o.status = 'completed'
    GROUP BY oi.category, oi.product
),
ranked AS (
    SELECT *, RANK() OVER (PARTITION BY category ORDER BY revenue DESC) AS rnk
    FROM product_revenue
)
SELECT category, product, revenue
FROM ranked
WHERE rnk <= 2;
