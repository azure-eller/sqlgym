select memid, translate(telephone, '-() ', '') as telephone
    from cd.members
    order by memid;
