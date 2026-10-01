For each category, find the top 2 products by revenue, where a product's revenue is the sum of quantity * unit_price across its order items. Only count orders with status 'completed'.

Keep ties: a product makes the list if fewer than 2 products in its category have strictly higher revenue, so a category can return more than 2 rows.

Return category, product, revenue.
