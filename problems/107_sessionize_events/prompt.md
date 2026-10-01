Split each user's events into sessions. A session starts with a user's first event, and a new session starts whenever more than 30 minutes have passed since that user's previous event. A gap of exactly 30 minutes stays in the same session.

Number each user's sessions 1, 2, 3, ... in time order.

Return user_id, session_number, session_start (first event time), session_end (last event time), event_count.
