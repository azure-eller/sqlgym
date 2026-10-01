select facid, sum(slots) as "Total Slots"
	from cd.bookings
	group by facid
order by facid;
