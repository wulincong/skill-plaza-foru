"""Synthetic in-memory relational SQL test fixture; no network or production writes."""
import sys
import json
import sqlite3
import re
x = json.load(sys.stdin)
c = sqlite3.connect(':memory:')
c.create_function('LOCATE', 2, lambda needle, haystack: haystack.find(needle)+1)
c.create_function('CONCAT', -1, lambda *a: ''.join(str(v) for v in a))
c.create_function('regexp', 2, lambda p, v: bool(re.search(p, v or '')))
c.executescript('CREATE TABLE c_company_position(id INTEGER PRIMARY KEY,publish_state TEXT,deleted INT,company_address_id INT,education TEXT,experience TEXT,type TEXT,name TEXT,update_time TEXT,company_archive_id INT,data_source TEXT,min_salary TEXT,max_salary TEXT,description TEXT,position_type TEXT); CREATE TABLE c_company_address(id INT PRIMARY KEY,province TEXT,city TEXT);')
c.executemany('INSERT INTO c_company_address VALUES(?,?,?)', [(10,'广东省','广州市'),(20,'浙江省','杭州市')])
rows = [
(1,'PUBLISHING',0,10,'DAZHUAN','GRADUATING','SHEZHAO','SLAM算法工程师','2026-10-31',100,'fixture','10','20','Python Python ROS2','1,42'),
(2,'PUBLISHING',0,20,'BENKE','LESS_THAN_3','SHEZHAO','调试算法工程师','2026-10-31',101,'fixture','5.5','6.5','python C++','42'),
(3,'PUBLISHING',0,None,'GAOZHI','BUXIAN','SHIXI','调试员','2026-10-30',100,'fixture',None,None,None,'42'),
(4,'PUBLISHING',0,10,None,None,'JIANZHI','销售','2026-10-30',None,None,'200','300','  ','77'),
(5,'CLOSED',0,10,'DAZHUAN','GRADUATING','SHEZHAO','算法工程师','2026-10-31',100,'fixture','10','20','Python','1'),
(6,'PUBLISHING',1,10,'DAZHUAN','GRADUATING','SHEZHAO','算法工程师','2026-10-31',100,'fixture','10','20','Python','1')]
if x.get('noSalary'):
    rows = [tuple(None if i in (11,12) else v for i,v in enumerate(row)) for row in rows]
if x.get('noDescription'):
    rows = [tuple(None if i == 13 else v for i,v in enumerate(row)) for row in rows]
if not x.get('empty'):
    c.executemany('INSERT INTO c_company_position VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
out = []
for job in x['jobs']:
    out.append(dict(job, rows=[json.loads(row[0])['row'] for row in c.execute(job['sql'])], completed=True, elapsedMs=0))
print(json.dumps(out, ensure_ascii=False))
