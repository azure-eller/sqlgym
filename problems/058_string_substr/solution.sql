select substr (mems.surname,1,1) as letter, count(*) as count 
    from cd.members mems
    group by letter
    order by letter
