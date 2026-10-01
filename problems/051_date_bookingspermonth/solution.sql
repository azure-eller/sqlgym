select date_trunc('month', starttime) as month, count(*)
	from cd.bookings
	group by month
	order by month
