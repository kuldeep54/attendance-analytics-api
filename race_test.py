import os
os.environ["MONGO_URI"]="mongodb://localhost:27017"
os.environ["MONGO_DB"]="attendance_test4"
import app.main as m
from fastapi.testclient import TestClient
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta
import threading

c=MongoClient("mongodb://localhost:27017",tz_aware=True)
db=c["attendance_test4"]
db.employees.delete_many({})
db.attendance_logs.delete_many({})
m.db=db
m.ensure_indexes()
client=TestClient(m.app)

def ist_to_ms(y,mo,d,h,mi,s=0):
    ist=timezone(timedelta(hours=5,minutes=30))
    return int(datetime(y,mo,d,h,mi,s,tzinfo=ist).timestamp()*1000)

client.post("/employees",json={"emp_code":"EMP0001","name":"A","email":"a@a.com","department":"Eng","joined_on":"2026-07-01"})

ms=ist_to_ms(2026,7,15,9,30)
# concurrent punch-in: 5 threads same emp/date
results=[]
def do_in():
    # need separate TestClient? TestClient is thread-safe? Use same?
    r=client.post("/attendance/punch-in",json={"emp_code":"EMP0001","punched_at":ms})
    results.append(r.status_code)

threads=[threading.Thread(target=do_in) for _ in range(5)]
[t.start() for t in threads]
[t.join() for t in threads]
print("punch-in race",results, "201 count",results.count(201),"409 count",results.count(409))

# concurrent punch-out
ms_out=ist_to_ms(2026,7,15,18,30)
results2=[]
def do_out():
    r=client.post("/attendance/punch-out",json={"emp_code":"EMP0001","punched_at":ms_out})
    results2.append(r.status_code)
threads=[threading.Thread(target=do_out) for _ in range(5)]
[t.start() for t in threads]
[t.join() for t in threads]
print("punch-out race",results2, "200 count",results2.count(200),"409 count",results2.count(409))

# concurrent duplicate employee create
results3=[]
def do_emp():
    r=client.post("/employees",json={"emp_code":"EMP0002","name":"B","email":"b@b.com","department":"Eng","joined_on":"2026-07-01"})
    results3.append(r.status_code)
threads=[threading.Thread(target=do_emp) for _ in range(5)]
[t.start() for t in threads]
[t.join() for t in threads]
print("emp race",results3)

# concurrent patch: two edits different fields, check history not lost
# create record
ms2=ist_to_ms(2026,7,16,9,30)
client.post("/attendance/punch-in",json={"emp_code":"EMP0001","punched_at":ms2})
ms2_out=ist_to_ms(2026,7,16,18,30)
client.post("/attendance/punch-out",json={"emp_code":"EMP0001","punched_at":ms2_out})
def do_patch1(res):
    r=client.patch("/attendance/EMP0001/2026-07-16",json={"punch_in":ist_to_ms(2026,7,16,9,28),"reason":"patch one reason","regularized_by":"hr1"})
    res.append(("p1",r.status_code))
def do_patch2(res):
    r=client.patch("/attendance/EMP0001/2026-07-16",json={"status":"WFH","reason":"patch two reason","regularized_by":"hr2"})
    res.append(("p2",r.status_code))
res=[]
t1=threading.Thread(target=do_patch1,args=(res,))
t2=threading.Thread(target=do_patch2,args=(res,))
t1.start();t2.start();t1.join();t2.join()
print("patch race",res)
r=client.get("/attendance?emp_code=EMP0001&date_from=2026-07-16&date_to=2026-07-16")
print(r.json()["items"][0]["history"])

print("done")
