with recursive recommendeds(memid) as (
	select memid from cd.members where recommendedby = 1
	union all
	select mems.memid
		from recommendeds recs
		inner join cd.members mems
			on mems.recommendedby = recs.memid
)
select recs.memid, mems.firstname, mems.surname
	from recommendeds recs
	inner join cd.members mems
		on recs.memid = mems.memid
order by memid
