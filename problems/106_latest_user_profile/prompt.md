The users table is append-only: every time a user changes their email, country or plan, a new row is added with a later updated_at. So a user can appear several times.

Return the current profile of every user, i.e. only their most recent row: user_id, email, country, plan.
