# REVIEW.md

| # | Where (function / line) | What is wrong | How you'd notice it (test, input, or symptom) | How you fixed it |
|---|---|---|---|---|
| 1 | `health` | Returns `{"status":"ok"}` without pinging MongoDB. Spec requires 200 only if Mongo answers, else 503. | Stop MongoDB, `GET /health` still returns 200. | `db.command("ping")` in try/except, raise 503 on failure. |
| 2 | `compute_late_minutes` | Checks `minutes > 10` on floored minutes instead of `seconds > 600`. Fails edge `09:40:01` (shift 09:30): floored minutes =10, returns 0, expected 10. | Punch at 09:40:01, `late_minutes` 0 instead of 10. | Rewrote as `compute_late_minutes` using `shift_start_dt` + `diff<=600→0 else diff//60`. |
| 3 | `compute_late_minutes` | Builds shift start via `punch_in.replace(hour,minute)` on naive datetime, no IST conversion, no overnight handling. | Overnight shift 22:00-06:00 punch 21:55 gives wrong diff. | Added `attendance_date_for_punch`, `shift_start_dt` in IST, `_is_overnight` check. |
| 4 | `compute_work_hours` | Uses `round()` (banker's rounding, float). R4 requires half-up. | 8442s =2.345h: `round` may give 2.34, expected 2.35. | Rewrote `compute_work_hours` with `Decimal(...).quantize(0.01, ROUND_HALF_UP)`. |
| 5 | `compute_overtime` | Returns any positive minutes, ignores R3 30-min minimum. Returns 5 for 5-min overtime, expected 0. | Punch out 18:35 (5 min over 18:30) returns 5 not 0. | Rewrote `compute_overtime` to return 0 unless `mins>=30`. |
| 6 | `compute_overtime` | Always uses attendance `date` for shift end, so overnight shift end lands on wrong day. Also mixes naive/aware datetimes. | Overnight 22:00-06:00: shift end put on start day 06:00, overtime huge. | Added `shift_end_dt` placing end next day when overnight, all datetimes UTC-aware. |
| 7 | All helpers | No truncation to seconds (R1). Millis stored. | Punch with 900ms: stored `...900`, expected `...000`. | Added `_ms_to_dt_trunc` / `_now_trunc` (`ms//1000*1000`), used everywhere. |
| 8 | `create_employee` | Check-then-insert (`find_one` then `insert_one`), no unique index. Concurrent duplicates both succeed. | Two parallel `POST /employees` same `emp_code` both 201. | Added `uniq_emp_code` unique index in `ensure_indexes`, catch `DuplicateKeyError`→409. |
| 9 | `create_employee` | `created_at=datetime.now()` naive, returned as datetime not epoch ms. | Response `created_at` ISO string not int. | Store `_now_trunc()` UTC, return via `emp_to_resp` with `_dt_to_ms`. |
| 10 | `EmployeeIn` | No validation: `emp_code` pattern, `email` pattern, `shift_start!=shift_end`, `joined_on` valid date. Invalid accepted. | `emp_code:BAD`, `email:bad`, same shift all 201. | Added `Field(pattern...)`, `field_validator` for `joined_on`, `model_validator` for shift differ. |
| 11 | `list_employees` | `skip=page*page_size` (should be `(page-1)*`), `total=count_documents({})` ignores filter, no sort, no page validation. | Page1 returns page2 data; filter total wrong; unordered. | Fixed skip, `count_documents(q)`, `.sort("emp_code")`, `Query(ge=1,le=100)`; return via `emp_to_resp`. |
| 12 | `punch_in` | No 404 for unknown employee (`emp["shift_start"]` →500). | Unknown `emp_code` gives 500 not 404. | Added `find_one` check →404. |
| 13 | `punch_in` | `datetime.fromtimestamp(...)` naive local, `d=ts.date()` not IST, no R1 overnight. | Server in different TZ gives wrong `date`. | Use `_ms_to_dt_trunc` (UTC) + `attendance_date_for_punch` (IST + overnight). |
| 14 | `PunchInIn` | `punched_at:Optional[int]`, `status:str` accept floats, seconds-values, `ABSENT`/`LEAVE`. | `punched_at:1234` or `status:LEAVE` accepted. | Changed to `EpochMillis StrictInt 1e11-4.1e12` + `status` validator allowing only `PRESENT,WFH,ON_DUTY`. |
| 15 | `punch_in` | Check-then-insert for `(emp_code,date)`, no unique index. Concurrent same-date punch-ins both 201. | Parallel punch-ins same date both 201. | Added `uniq_emp_date` unique index, catch `DuplicateKeyError`→409. Return via `att_to_resp`, no `id` field. |
| 16 | `list_attendance` | `list(find(q))` loads all (~100k) into memory, Python sort only by `date`, slices in Python. Slow, wrong order. | 100k docs slow; same-date order random. | Use `.sort([("date",-1),("emp_code",1)]).skip().limit()`, `count_documents(q)`. |
| 17 | `list_attendance` | Adds `d["id"]=str(_id)`, returns datetimes not epoch ms, ignores missing `history`/`half_day`. | Response has `id`, ISO dates. | Return via `att_to_resp` (no `_id`/`id`, ms conversion, missing→defaults). No validation for `date_from>date_to`, `status`. |
| 18 | Global | No `ensure_indexes()` at startup, `MongoClient` without `tz_aware=True`. Grader expects `IXSCAN` no `COLLSCAN`; naive datetimes ambiguous. | `explain` shows `COLLSCAN`. | Added `ensure_indexes()` (9 indexes, idempotent, called at import + startup), `MongoClient(...,tz_aware=True)`. |

## Not defects

- `load_dotenv()` default `override=False`: real env wins over `.env`, matches spec. Kept.
- `IST=timezone(timedelta(hours=5,minutes=30))`: correct fixed offset, no DST in IST. Kept.
- `status` default `PRESENT` in punch-in and `history:[]`, `overtime:0`, `half_day:False` defaults: match DATA_MODEL for open records. Kept.
