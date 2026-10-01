select memid, telephone from cd.members where regexp_matches(telephone, '[()]');
