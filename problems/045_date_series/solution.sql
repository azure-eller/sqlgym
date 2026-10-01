select unnest(generate_series(timestamp '2012-10-01', timestamp '2012-10-31', interval '1 day')) as ts;
