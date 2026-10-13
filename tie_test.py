import os
os.environ["MONGO_URI"]="mongodb://localhost:27017"
os.environ["MONGO_DB"]="attendance_test3"
import app.main as m
from fastapi.testclient import TestClient
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta
c=MongoClient("mongodb://localhost:27017",tz_aware=True)
db=c["attendance_test3"]
db.employees.delete_many({})
db.attendance_logs.delete_many({})
m.db=db
m.ensure_indexes()
client=TestClient(m.app)

def ist_to_ms(y,mo,d,h,mi,s=0):
    ist=timezone(timedelta(hours=5,minutes=30))
    return int(datetime(y,mo,d,h,mi,s,tzinfo=ist).timestamp()*1000)

# create depts
for ec,name,dept,joined in [
    ("EMP0001","A","Engineering","2026-07-01"),
    ("EMP0002","B","Engineering","2026-07-01"),
    ("EMP0003","C","Engineering","2026-07-01"),
    ("EMP0004","D","Engineering","2026-07-20"),  # mid-month joiner
    ("EMP0005","E","Sales","2026-07-01"),  # zero logs
    ("EMP0006","F","Support","2026-07-01"),  # overnight
]:
    shift_start="22:00" if ec=="EMP0006" else "09:30"
    shift_end="06:00" if ec=="EMP0006" else "18:30"
    r=client.post("/employees",json={"emp_code":ec,"name":name,"email":f"{ec}@x.com","department":dept,"shift_start":shift_start,"shift_end":shift_end,"joined_on":joined})
    print(ec,r.status_code)

# punch-ins for tie test: EMP0001 late 20, EMP0002 late 20 (tie), EMP0003 late 10
# shift 09:30, late 20 => punch 09:50? diff 20min => 09:50. late 10? Actually need >10:00, so 09:50 diff 20 => late 20. Good.
# For tie at cutoff: limit=1, two tied at rank 1? Actually if two tied for first with same total, both rank 1, limit 1 should return both.
# Let's create:
# EMP0001: 2026-07-07 09:50 (late 20)
# EMP0002: 2026-07-07 09:50 (late 20)
# EMP0003: 2026-07-08 09:40:01 (late 10)
for ec,day,h,mi,s in [
    ("EMP0001",7,9,50,0),
    ("EMP0002",7,9,50,0),
    ("EMP0003",8,9,40,1),
]:
    ms=ist_to_ms(2026,7,day,h,mi,s)
    r=client.post("/attendance/punch-in",json={"emp_code":ec,"punched_at":ms})
    print(f"punch {ec} {day}",r.status_code,r.json().get("late_minutes") if r.status_code==201 else r.json())
    # punch out 18:30 (no overtime)
    ms_out=ist_to_ms(2026,7,day,18,30)
    r2=client.post("/attendance/punch-out",json={"emp_code":ec,"punched_at":ms_out})
    print(f"  out {r2.status_code}")

# leaderboard limit 1 should return both tied rank 1 (2 rows)
r=client.get("/analytics/leaderboard/late?month=2026-07&limit=1")
print("leaderboard limit1 tie",r.json())
# limit 2 should return? ranks: 1,1,3? Since standard competition ranking 1,1,3 (skip 2). limit 2 should return rank<=2 => both rank1 (2 rows), not rank3. Good.
r=client.get("/analytics/leaderboard/late?month=2026-07&limit=2")
print("limit2",r.json())
r=client.get("/analytics/leaderboard/late?month=2026-07&limit=3")
print("limit3",r.json())

# weekend test: punch Saturday 2026-07-11 (Saturday? Check: July 11 2026 Saturday? July 1 Wed, so 4 Sat, 5 Sun, 11 Sat yes)
ms_sat_in=ist_to_ms(2026,7,11,9,50)
r=client.post("/attendance/punch-in",json={"emp_code":"EMP0001","punched_at":ms_sat_in})
print("sat punch",r.status_code,r.json() if r.status_code!=201 else r.json()["late_minutes"])
ms_sat_out=ist_to_ms(2026,7,11,18,30)
r=client.post("/attendance/punch-out",json={"emp_code":"EMP0001","punched_at":ms_sat_out})
print("sat out",r.status_code)

# monthly for EMP0001: present should exclude weekend, late should include weekend
r=client.get("/analytics/employees/EMP0001/monthly?month=2026-07")
print("monthly emp1 weekend",r.json())
# working_days for EMP0004 joined 20th: July 20 Mon? July 20 2026 Mon? July 1 Wed, 20 Mon yes. Working days from 20-31: 20,21,22,23,24,27,28,29,30,31 =10? (25-26 weekend). Let's see.
r=client.get("/analytics/employees/EMP0004/monthly?month=2026-07")
print("mid joiner",r.json())
# zero logs EMP0005
r=client.get("/analytics/employees/EMP0005/monthly?month=2026-07")
print("zero logs monthly",r.json())
# dept summary should include zero-log headcount
r=client.get("/analytics/departments/summary?month=2026-07")
print("dept summary zero logs",r.json())

# overnight punch-out across midnight
# EMP0006 shift 22-06, punch-in 2026-07-06 21:55 IST, punch-out 2026-07-07 06:40 IST
ms_in=ist_to_ms(2026,7,6,21,55)
r=client.post("/attendance/punch-in",json={"emp_code":"EMP0006","punched_at":ms_in})
print("overnight in",r.status_code,r.json() if r.status_code!=201 else (r.json()["date"],r.json()["late_minutes"]))
ms_out=ist_to_ms(2026,7,7,6,40)
r=client.post("/attendance/punch-out",json={"emp_code":"EMP0006","punched_at":ms_out})
print("overnight out",r.status_code,r.json() if r.status_code!=200 else (r.json()["work_hours"],r.json()["overtime_minutes"]))

# half-day: 3.5h => half true, counts 0.5
# create EMP0007? Use EMP0003 with short day
ms_in2=ist_to_ms(2026,7,9,9,30)
client.post("/attendance/punch-in",json={"emp_code":"EMP0003","punched_at":ms_in2})
ms_out2=ist_to_ms(2026,7,9,13,0)  # 3.5h
r=client.post("/attendance/punch-out",json={"emp_code":"EMP0003","punched_at":ms_out2})
print("half day",r.json() if r.status_code==200 else r.status_code)
r=client.get("/analytics/employees/EMP0003/monthly?month=2026-07")
print("half monthly",r.json())

# rounding half-up: work_hours edge? e.g., seconds 17999? 17999/3600=4.9997... rounds 5.0? Need half case: find seconds where third decimal exactly 5.
# Example: 1.005 should round to 1.01 half-up, but bankers would round to 1.00? Python round(1.005,2)=1.0? Actually float issues. Our Decimal should handle.
# Test compute_work_hours for 2.345h? 2.345*3600=8442 sec. 8442/3600=2.345 -> should round 2.35 half-up.
from datetime import timezone as tz
pin=datetime(2026,7,1,0,0,0,tzinfo=tz.utc)
pout=datetime(2026,7,1,2,20,42,tzinfo=tz.utc)  # 2h20m42s = 8442s
print("wh half-up test",m.compute_work_hours(pin,pout),"exp 2.35")
print("py round",round(8442/3600,2),"bankers would give 2.34?")

print("done")
