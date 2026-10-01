WITH active_days AS (
    SELECT DISTINCT user_id, event_time::DATE AS day
    FROM events
),
grouped AS (
    SELECT user_id, day,
           day - CAST(ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY day) AS INTEGER) AS island
    FROM active_days
)
SELECT user_id, MIN(day) AS streak_start, MAX(day) AS streak_end, COUNT(*) AS days
FROM grouped
GROUP BY user_id, island
HAVING COUNT(*) >= 2;
