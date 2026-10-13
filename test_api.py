"""Quick smoke tests for the Attendance API."""
import requests
import sys

BASE = "http://localhost:8000"
errors = []

def check(label, condition, detail=""):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label} -- {detail}")
        errors.append(label)

# 1. Health
r = requests.get(f"{BASE}/health")
check("Health", r.status_code == 200, f"got {r.status_code}")

# 2. List employees
r = requests.get(f"{BASE}/employees")
check("List employees", r.status_code == 200 and r.json()["total"] >= 6, f"got {r.status_code}")

# 3. Create employee
r = requests.post(f"{BASE}/employees", json={
    "emp_code": "EMP9999",
    "name": "Test User",
    "email": "test@example.com",
    "department": "QA",
    "joined_on": "2026-01-01"
})
check("Create employee", r.status_code == 201, f"got {r.status_code} {r.text}")
if r.status_code == 201:
    body = r.json()
    check("Employee created_at is int", isinstance(body["created_at"], int), f"type={type(body['created_at'])}")
    check("No _id in response", "_id" not in body and "id" not in body, f"keys={list(body.keys())}")

# 4. Duplicate employee
r = requests.post(f"{BASE}/employees", json={
    "emp_code": "EMP9999",
    "name": "Test User",
    "email": "test@example.com",
    "department": "QA",
    "joined_on": "2026-01-01"
})
check("Duplicate employee -> 409", r.status_code == 409, f"got {r.status_code}")

# 5. Punch in
r = requests.post(f"{BASE}/attendance/punch-in", json={
    "emp_code": "EMP9999",
    "punched_at": 1783312500000
})
check("Punch in", r.status_code == 201, f"got {r.status_code} {r.text}")
if r.status_code == 201:
    body = r.json()
    check("Punch-in punch_in is int", isinstance(body["punch_in"], int))
    check("Punch-in no _id", "_id" not in body and "id" not in body)
    check("Punch-in late_minutes computed", "late_minutes" in body)
    print(f"    punch_in record: date={body['date']} late={body['late_minutes']}")

# 6. Duplicate punch in
r = requests.post(f"{BASE}/attendance/punch-in", json={
    "emp_code": "EMP9999",
    "punched_at": 1783312500000
})
check("Duplicate punch in -> 409", r.status_code == 409, f"got {r.status_code}")

# 7. Punch out
r = requests.post(f"{BASE}/attendance/punch-out", json={
    "emp_code": "EMP9999",
    "punched_at": 1783344900000
})
check("Punch out", r.status_code == 200, f"got {r.status_code} {r.text}")
if r.status_code == 200:
    body = r.json()
    check("Work hours computed", body["work_hours"] is not None)
    check("half_day is bool", isinstance(body["half_day"], bool))
    print(f"    work_hours={body['work_hours']} overtime={body['overtime_minutes']} half_day={body['half_day']}")

# 8. Duplicate punch out -> 409
r = requests.post(f"{BASE}/attendance/punch-out", json={
    "emp_code": "EMP9999",
    "punched_at": 1783344900000
})
check("Duplicate punch out -> 409", r.status_code == 409, f"got {r.status_code}")

# 9. List attendance
r = requests.get(f"{BASE}/attendance", params={"emp_code": "EMP9999"})
check("List attendance", r.status_code == 200 and r.json()["total"] >= 1, f"got {r.status_code}")

# 10. Employee monthly
r = requests.get(f"{BASE}/analytics/employees/EMP0001/monthly", params={"month": "2026-07"})
check("Employee monthly", r.status_code == 200, f"got {r.status_code} {r.text}")
if r.status_code == 200:
    body = r.json()
    print(f"    EMP0001 Jul: working_days={body['working_days']} present_days={body['present_days']} attendance_pct={body['attendance_pct']}")

# 11. Department summary
r = requests.get(f"{BASE}/analytics/departments/summary", params={"month": "2026-07"})
check("Dept summary", r.status_code == 200, f"got {r.status_code} {r.text}")
if r.status_code == 200:
    for item in r.json()["items"]:
        print(f"    {item['department']}: headcount={item['headcount']} present={item['present_days']} avg_wh={item['avg_work_hours']}")

# 12. Late leaderboard
r = requests.get(f"{BASE}/analytics/leaderboard/late", params={"month": "2026-07"})
check("Late leaderboard", r.status_code == 200, f"got {r.status_code} {r.text}")
if r.status_code == 200:
    for item in r.json()["items"]:
        print(f"    rank={item['rank']} {item['emp_code']} {item['name']}: {item['total_late_minutes']}min")

# 13. Department trend
r = requests.get(f"{BASE}/analytics/departments/Engineering/trend", params={"from": "2026-07-06", "to": "2026-07-10"})
check("Dept trend", r.status_code == 200, f"got {r.status_code} {r.text}")
if r.status_code == 200:
    items = r.json()["items"]
    check("Trend has 5 days", len(items) == 5, f"got {len(items)}")
    for item in items:
        print(f"    {item['date']}: wd={item['is_working_day']} hc={item['headcount']} present={item['present_count']} rate={item['attendance_rate']} ma7={item['moving_avg_7d']}")

# 14. Regularize
r = requests.patch(f"{BASE}/attendance/EMP9999/2026-07-06", json={
    "reason": "biometric failure during entry",
    "regularized_by": "hr.admin",
    "punch_in": 1783311000000
})
check("Regularize", r.status_code == 200, f"got {r.status_code} {r.text}")
if r.status_code == 200:
    body = r.json()
    check("History appended", len(body["history"]) == 1)
    print(f"    late={body['late_minutes']} work_hours={body['work_hours']} history_entries={len(body['history'])}")

# 15. Explain
r = requests.get(f"{BASE}/admin/explain/attendance_list", params={"emp_code": "EMP0001"})
check("Explain", r.status_code == 200, f"got {r.status_code} {r.text}")

# 16. Unknown employee -> 404
r = requests.get(f"{BASE}/analytics/employees/EMP0000/monthly", params={"month": "2026-07"})
check("Unknown employee -> 404", r.status_code == 404, f"got {r.status_code}")

# 17. Invalid epoch ms -> 422
r = requests.post(f"{BASE}/attendance/punch-in", json={
    "emp_code": "EMP0001",
    "punched_at": 1234
})
check("Invalid epoch ms -> 422", r.status_code == 422, f"got {r.status_code}")

# 18. Unknown dept trend -> 404
r = requests.get(f"{BASE}/analytics/departments/FakeDept/trend", params={"from": "2026-07-01", "to": "2026-07-10"})
check("Unknown dept -> 404", r.status_code == 404, f"got {r.status_code}")

# 19. Invalid date range
r = requests.get(f"{BASE}/attendance", params={"date_from": "2026-08-01", "date_to": "2026-07-01"})
check("date_from > date_to -> 422", r.status_code == 422, f"got {r.status_code}")

# 20. No-change regularize -> 422
r = requests.patch(f"{BASE}/attendance/EMP9999/2026-07-06", json={
    "reason": "testing no change",
    "regularized_by": "hr.admin"
})
check("No-change regularize -> 422", r.status_code == 422, f"got {r.status_code}")

# Summary
print(f"\n{'='*50}")
if errors:
    print(f"FAILED: {len(errors)} test(s)")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("ALL TESTS PASSED!")
