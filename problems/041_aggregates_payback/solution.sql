select 	facs.name as name,
	facs.initialoutlay/((sum(case
			when memid = 0 then slots * facs.guestcost
			else slots * membercost
		end)/3) - facs.monthlymaintenance) as months
	from cd.bookings bks
	inner join cd.facilities facs
		on bks.facid = facs.facid
	group by facs.facid, facs.name, facs.initialoutlay, facs.monthlymaintenance
order by name;
