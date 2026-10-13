import os
os.environ["MONGO_URI"]="mongodb://localhost:27017"
os.environ["MONGO_DB"]="attendance_test2"
import app.main as m
from fastapi.testclient import TestClient
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta
import pathlib
from bson import json_util

c=MongoClient("mongodb://localhost:27017",tz_aware=True)
db=c["attendance_test2"]
db.employees.delete_many({})
db.attendance_logs.delete_many({})
m.db=db  # override? need to also override app.main db reference? TestClient uses m.app which uses m.db global. We replaced m.db, good.
# need to re-ensure indexes on new db? ensure_indexes uses global db which we replaced? Actually m.db is db, ensure uses db global variable (which is m.db). Since we set m.db=db, ensure will use new.
m.ensure_indexes()
# But m.db still points to old? We set m.db=db (same object? Actually db is new DB object). Need to also set m.client? Not needed.
# Reimport? The functions use global `db` variable in module, which we updated via m.db=db. Good.

client=TestClient(m.app)

def ist_to_ms(y,mo,d,h,mi,s=0,ms=0):
    ist=timezone(timedelta(hours=5,minutes=30))
    dt_ist=datetime(y,mo,d,h,mi,s,ms*1000,tzinfo=ist)
    return int(dt_ist.timestamp()*1000)

# seed sample
opts=json_util.JSONOptions(tz_aware=True)
for name in ("employees","attendance_logs"):
    docs=json_util.loads((pathlib.Path("sample_data")/f"{name}.json").read_text(), json_options=opts)
    if docs:
        db[name].insert_many(docs)
print("seeded",db.employees.count_documents({}),db.attendance_logs.count_documents({}))

def check(name,resp,exp_status):
    ok="OK" if resp.status_code==exp_status else f"FAIL exp {exp_status}"
    print(f"{name}: {resp.status_code} {ok} - {str(resp.json())[:200]}")
    return resp

# 1. create duplicate
r=client.post("/employees",json={"emp_code":"EMP0001","name":"X","email":"x@x.com","department":"Eng","joined_on":"2026-01-01"})
check("dup emp",r,409)
# invalid emp_code
r=client.post("/employees",json={"emp_code":"BAD","name":"X","email":"x@x.com","department":"Eng","joined_on":"2026-01-01"})
check("bad emp_code",r,422)
# shift same
r=client.post("/employees",json={"emp_code":"EMP0100","name":"X","email":"x@x.com","department":"Eng","shift_start":"09:00","shift_end":"09:00","joined_on":"2026-01-01"})
check("same shift",r,422)
# bad email
r=client.post("/employees",json={"emp_code":"EMP0100","name":"X","email":"bad","department":"Eng","joined_on":"2026-01-01"})
check("bad email",r,422)

# list pagination
r=client.get("/employees?page=1&page_size=2")
print("list page1",r.json())
r=client.get("/employees?page=0")
check("page 0",r,422)
r=client.get("/employees?page_size=101")
check("page_size 101",r,422)

# punch-in unknown
r=client.post("/attendance/punch-in",json={"emp_code":"EMP9999","punched_at":ist_to_ms(2026,7,15,9,30)})
check("punch unknown",r,404)
# punch invalid status
r=client.post("/attendance/punch-in",json={"emp_code":"EMP0001","punched_at":ist_to_ms(2026,7,15,9,30),"status":"LEAVE"})
check("punch LEAVE",r,422)
# punch seconds-looking
r=client.post("/attendance/punch-in",json={"emp_code":"EMP0001","punched_at":1750000000})
check("punch seconds",r,422)
# punch float
r=client.post("/attendance/punch-in",json={"emp_code":"EMP0001","punched_at":1783312500000.5})
check("punch float",r,422)
# punch string
r=client.post("/attendance/punch-in",json={"emp_code":"EMP0001","punched_at":"1783312500000"})
check("punch string",r,422)
# punch truncation: 09:40:00.900 should store as 09:40:00
ms_with_ms=ist_to_ms(2026,7,20,9,40,0,900)  # 900ms
print("ms with ms",ms_with_ms)
r=client.post("/attendance/punch-in",json={"emp_code":"EMP0002","punched_at":ms_with_ms})
print("trunc punch",r.status_code,r.json())
if r.status_code==201:
    j=r.json()
    print("stored punch_in",j["punch_in"], "expected", (ms_with_ms//1000*1000), "match", j["punch_in"]==(ms_with_ms//1000*1000))
    print("late",j["late_minutes"],"exp 0")

# punch-out validations
# unknown emp
r=client.post("/attendance/punch-out",json={"emp_code":"EMP9999"})
check("out unknown",r,404)
# no punch-in: create fresh emp
client.post("/employees",json={"emp_code":"EMP0200","name":"N","email":"n@n.com","department":"Eng","joined_on":"2026-07-01"})
r=client.post("/attendance/punch-out",json={"emp_code":"EMP0200","punched_at":ist_to_ms(2026,7,15,18,0)})
check("out no punch",r,404)
# already punched out: use EMP0001 2026-07-06 which is closed
# need punched_at after punch_in: use 2026-07-06 19:00
r=client.post("/attendance/punch-out",json={"emp_code":"EMP0001","punched_at":ist_to_ms(2026,7,6,19,0)})
check("out already closed (most recent <=? )",r,409)  # most recent <= 19:00 on 6th? EMP0001 has 06 and 07. Most recent <= 06 19:00 is 06 record which is closed ->409. Good.

# punch-out <= punch_in
# create open record
client.post("/employees",json={"emp_code":"EMP0201","name":"N","email":"n1@n.com","department":"Eng","joined_on":"2026-07-01"})
ms_in=ist_to_ms(2026,7,21,9,30)
client.post("/attendance/punch-in",json={"emp_code":"EMP0201","punched_at":ms_in})
r=client.post("/attendance/punch-out",json={"emp_code":"EMP0201","punched_at":ms_in})  # equal
check("out equal",r,422)
r=client.post("/attendance/punch-out",json={"emp_code":"EMP0201","punched_at":ms_in-1000})
check("out before",r,422)
# >24h
r=client.post("/attendance/punch-out",json={"emp_code":"EMP0201","punched_at":ms_in+25*3600*1000})
check("out >24h",r,422)
# valid
r=client.post("/attendance/punch-out",json={"emp_code":"EMP0201","punched_at":ms_in+8*3600*1000})
check("out valid",r,200)
# second out ->409
r=client.post("/attendance/punch-out",json={"emp_code":"EMP0201","punched_at":ms_in+9*3600*1000})
check("out dup",r,409)

# list attendance filters
r=client.get("/attendance?date_from=2026-07-10&date_to=2026-07-01")
check("date_from>to",r,422)
r=client.get("/attendance?status=BAD")
check("bad status",r,422)
r=client.get("/attendance?page_size=100")
print("page_size 100 ok",r.status_code)
# check sort: date desc, emp_code asc
r=client.get("/attendance?page=1&page_size=20")
items=r.json()["items"]
print("sort check first 3",[(i["date"],i["emp_code"]) for i in items[:3]])
# verify descending date
dates=[i["date"] for i in items]
print("dates desc?",dates==sorted(dates,reverse=True))

# patch tests
# get EMP0003 2026-07-06 (late 35)
r=client.get("/attendance?emp_code=EMP0003")
print("emp0003",r.json())
# regularize: change punch_in from 10:05 to 09:28 (like sample 8)
ms_new=ist_to_ms(2026,7,6,9,28)
r=client.patch("/attendance/EMP0003/2026-07-06",json={"punch_in":ms_new,"reason":"correct time","regularized_by":"hr.admin"})
print("patch",r.status_code,r.json())
if r.status_code==200:
    j=r.json()
    print("new late",j["late_minutes"],"history",j["history"])
# patch no change ->422
r=client.patch("/attendance/EMP0003/2026-07-06",json={"punch_in":ms_new,"reason":"again?","regularized_by":"hr"})
print("patch no change? should be 422 if same",r.status_code,r.json())
# patch ABSENT with punch_in ->422
r=client.patch("/attendance/EMP0001/2026-07-06",json={"status":"ABSENT","punch_in":ms_new,"reason":"absent test reason","regularized_by":"hr"})
check("patch absent+punch",r,422)
# patch to ABSENT (valid) clears times
r=client.patch("/attendance/EMP0001/2026-07-06",json={"status":"ABSENT","reason":"marked absent now","regularized_by":"hr.admin"})
print("patch to absent",r.status_code,r.json())
# patch presence without punch_in (record is now ABSENT, try set PRESENT without punch) ->422?
# ABSENT record has no punch_in, try set PRESENT without supplying punch_in
r=client.patch("/attendance/EMP0001/2026-07-06",json={"status":"PRESENT","reason":"back to present","regularized_by":"hr.admin"})
check("patch present no punch",r,422)
# patch punch_in wrong date ->422 (move to different date)
ms_other=ist_to_ms(2026,7,7,9,30)
r=client.patch("/attendance/EMP0002/2026-07-14",json={"punch_in":ms_other,"reason":"wrong date test","regularized_by":"hr"})
check("patch wrong date",r,422)
# 404 unknown emp/date
r=client.patch("/attendance/EMP9999/2026-07-06",json={"status":"ABSENT","reason":"test reason long","regularized_by":"hr"})
check("patch unknown emp",r,404)
r=client.patch("/attendance/EMP0001/2026-07-30",json={"status":"ABSENT","reason":"test reason long","regularized_by":"hr"})
check("patch unknown date",r,404)
# reason too short ->422
r=client.patch("/attendance/EMP0004/2026-07-07",json={"status":"PRESENT","reason":"bad","regularized_by":"hr"})
check("patch short reason",r,422)

# analytics 404
r=client.get("/analytics/employees/EMP9999/monthly?month=2026-07")
check("monthly unknown",r,404)
r=client.get("/analytics/departments/NoDept/trend?from=2026-07-01&to=2026-07-05")
check("trend unknown dept",r,404)
r=client.get("/analytics/departments/Engineering/trend?from=2026-07-10&to=2026-07-01")
check("trend to<from",r,422)
r=client.get("/analytics/departments/Engineering/trend?from=2026-01-01&to=2026-06-01")
check("trend >92",r,422)

# explain
for ep,qs in [
    ("attendance_list",""),
    ("employee_monthly","?emp_code=EMP0001&month=2026-07"),
    ("department_summary","?month=2026-07"),
    ("late_leaderboard","?month=2026-07"),
    ("department_trend","?department=Engineering&from=2026-07-06&to=2026-07-14"),
]:
    r=client.get(f"/admin/explain/{ep}{qs}")
    print(f"explain {ep}",r.status_code)
    if r.status_code==200:
        j=r.json()
        s=str(j["explain"])
        has_ix="IXSCAN" in s
        has_coll="COLLSCAN" in s
        print(f"  IXSCAN={has_ix} COLLSCAN={has_coll} {'OK' if has_ix and not has_coll else 'FAIL'}")
    else:
        print(r.json())
# explain missing params
r=client.get("/admin/explain/employee_monthly?month=2026-07")
check("explain missing emp",r,422)
r=client.get("/admin/explain/department_trend?department=Engineering&from=2026-07-01")
check("explain missing to",r,422)

print("done")
