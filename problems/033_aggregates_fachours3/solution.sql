select facs.facid, facs.name,
	printf('%.2f', sum(bks.slots)/2.0) as "Total Hours"

	from cd.bookings bks
	inner join cd.facilities facs
		on facs.facid = bks.facid
	group by facs.facid, facs.name
order by facs.facid;
