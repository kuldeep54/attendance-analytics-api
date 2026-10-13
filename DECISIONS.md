# DECISIONS.md

1. **Indexes.** `uniq_emp_code` enforces emp uniqueness and speeds all emp lookups. `dept_empcode` serves list-employees filter+sort. `dept_joined` and `joined_on` serve headcount queries with and without department filter. `uniq_emp_date` guarantees one record per day and makes punch-in race-safe plus monthly match fast. `date_desc_emp` matches attendance-list sort. `date_asc` and `date_late` cover month-range and leaderboard filters. `emp_punchin` finds the punch-out target. I considered a `status` index but rejected it: only five values, low selectivity, date indexes already give IXSCAN.

2. **Punch-in race.** Both requests go straight to `insert_one` without a prior check. The unique `(emp_code,date)` index accepts one insert; the other raises `DuplicateKeyError`, which I catch and return as 409.

3. **Ties.** I use `$rank` (competition ranking): ties share a rank and the next rank skips. I filter `rank<=limit` after ranking, so tied rows at the cutoff all return, possibly more than `limit` rows, ordered by late desc then emp_code.

4. **Headcount.** I aggregate from `employees` with `joined_on<=month-end`, grouping by department. This does not touch logs, so zero-log employees still count.

5. **One change at 100x:** precompute monthly summaries in a background job into a summary collection, so reads become single-document lookups.
