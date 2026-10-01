WITH flagged AS (
    SELECT user_id, event_time,
           CASE
               WHEN event_time - LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time)
                    <= INTERVAL 30 MINUTE THEN 0
               ELSE 1
           END AS new_session
    FROM events
),
numbered AS (
    SELECT user_id, event_time,
           SUM(new_session) OVER (PARTITION BY user_id ORDER BY event_time) AS session_number
    FROM flagged
)
SELECT user_id, session_number,
       MIN(event_time) AS session_start,
       MAX(event_time) AS session_end,
       COUNT(*) AS event_count
FROM numbered
GROUP BY user_id, session_number;
