# Employee Attendance & Analytics API

FastAPI + MongoDB implementation of the HROne assignment: punch-in/out with R1-R5, manual corrections with audit trail, and analytics via aggregation pipelines.

## Run

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
# set env (or create .env, env vars win):
# Windows PowerShell: $env:MONGO_URI="mongodb://localhost:27017"; $env:MONGO_DB="attendance_db"
# Linux/Mac: export MONGO_URI=mongodb://localhost:27017 MONGO_DB=attendance_db
# optional local mongo:
# docker run -d -p 27017:27017 --name mongo mongo:7
uvicorn app.main:app --port 8000
```

`GET /health` returns 200 only when MongoDB pings OK, else 503. All indexes are created at startup.

## Env

- `MONGO_URI` (default `mongodb://localhost:27017`)
- `MONGO_DB` (default `attendance_db`)

## Notes

All endpoints in `openapi.yaml` are implemented, including R1-R10, `$densify` trend with 7-day moving average, `$rank` leaderboard with competition ranking, and `/admin/explain/{endpoint}` showing `IXSCAN` no `COLLSCAN`.

Nothing is missing.
