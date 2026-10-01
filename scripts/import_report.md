# pgexercises import report

Imported 62 problems.

## Solutions rewritten for DuckDB

- `aggregates/fachours3` (List the total hours booked per named facility)
  - `trim(to_char(sum(bks.slots)/2.0, '9999999999999999D99'))` → `printf('%.2f', sum(bks.slots)/2.0)`
- `aggregates/rankmembers` (Rank members by (rounded) hours used)
  - `((sum(bks.slots)+10)/20)*10 as` → `((sum(bks.slots)+10)//20)*10 as`
  - `((sum(bks.slots)+10)/20)*10 desc` → `((sum(bks.slots)+10)//20)*10 desc`
  - `group by mems.memid` → `group by mems.memid, firstname, surname`
- `aggregates/payback` (Calculate the payback time for each facility)
  - `group by facs.facid` → `group by facs.facid, facs.name, facs.initialoutlay, facs.monthlymaintenance`
- `aggregates/rollingavg` (Calculate a rolling average of total revenue)
  - `cast(generate_series(timestamp '2012-08-01', '2012-08-31','1 day') as date)` → `cast(unnest(generate_series(timestamp '2012-08-01', timestamp '2012-08-31', interval '1 day')) as date)`
- `date/series` (Generate a list of all the dates in October 2012)
  - `select generate_series(` → `select unnest(generate_series(`
  - `) as ts` → `)) as ts`
- `date/interval2` (Work out the number of seconds between timestamps)
  - `- '2012-08-31 01:00:00'` → `- timestamp '2012-08-31 01:00:00'`
- `date/daysinmonth` (Work out the number of days in each month of 2012)
  - `select generate_series(` → `select unnest(generate_series(`
  - `interval '1 month') as month` → `interval '1 month')) as month`
- `date/utilisationpermonth` (Work out the utilisation percentage for each facility by month)
  - `group by facs.facid, month` → `group by facs.facid, facs.name, month`
- `string/reg` (Find telephone numbers with parentheses)
  - `telephone ~ '[()]'` → `regexp_matches(telephone, '[()]')`

## ORDER BY leaves ties, so row order is not checked

- `joins/simplejoin2` (Work out the start times of bookings for tennis courts)
- `joins/threejoin2` (Produce a list of costly bookings)
- `joins/tjsub` (Produce a list of costly bookings, using a subquery)

## Skipped

- `updates/insert` (Insert some data into a table): modifies data (INSERT/UPDATE/DELETE); sqlgym only checks SELECT results
- `updates/insert2` (Insert multiple rows of data into a table): modifies data (INSERT/UPDATE/DELETE); sqlgym only checks SELECT results
- `updates/insert3` (Insert calculated data into a table): modifies data (INSERT/UPDATE/DELETE); sqlgym only checks SELECT results
- `updates/update` (Update some existing data): modifies data (INSERT/UPDATE/DELETE); sqlgym only checks SELECT results
- `updates/updatemultiple` (Update multiple rows and columns at the same time): modifies data (INSERT/UPDATE/DELETE); sqlgym only checks SELECT results
- `updates/updatecalculated` (Update a row based on the contents of another row): modifies data (INSERT/UPDATE/DELETE); sqlgym only checks SELECT results
- `updates/delete` (Delete all bookings): modifies data (INSERT/UPDATE/DELETE); sqlgym only checks SELECT results
- `updates/deletewh` (Delete a member from the cd.members table): modifies data (INSERT/UPDATE/DELETE); sqlgym only checks SELECT results
- `updates/deletewh2` (Delete based on a subquery): modifies data (INSERT/UPDATE/DELETE); sqlgym only checks SELECT results
