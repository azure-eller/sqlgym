select starttime, starttime + slots*(interval '30 minutes') endtime
	from cd.bookings
	order by endtime desc, starttime desc
	limit 10
