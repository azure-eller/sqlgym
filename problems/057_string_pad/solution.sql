select lpad(cast(zipcode as char(5)),5,'0') zip from cd.members order by zip
