SELECT user_id, email, country, plan
FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY updated_at DESC) AS rn
    FROM users
) AS ranked
WHERE rn = 1;
