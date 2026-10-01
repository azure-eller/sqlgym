select row_number() over(order by joindate), firstname, surname
	from cd.members
order by joindate
