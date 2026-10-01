select 	extract(month from cal.month) as month,
	(cal.month + interval '1 month') - cal.month as length
	from
	(
		select unnest(generate_series(timestamp '2012-01-01', timestamp '2012-12-01', interval '1 month')) as month
	) cal
order by month;
