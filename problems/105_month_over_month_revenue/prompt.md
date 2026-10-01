For each month with completed orders, return the month's revenue, the previous month's revenue, and the percent change between them. Revenue is quantity * unit_price summed over order items. Only count orders with status 'completed'.

pct_change is 100 * (revenue - prev_revenue) / prev_revenue, so +12.5% is 12.5. For the first month, prev_revenue and pct_change are NULL.

Return month (the first day of the month, as a DATE), revenue, prev_revenue, pct_change, sorted by month.
