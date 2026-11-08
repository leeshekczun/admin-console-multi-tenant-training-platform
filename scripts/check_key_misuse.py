"""A3 regression: an existing key conflicts before validating a replacement course."""
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient
from backend.main import app
from backend.db import connect

assert os.getenv('MYSQL_DATABASE')=='certificate_admin_test','Use the isolated test database'
client=TestClient(app)
headers={'X-Actor':'alice@east.test','Idempotency-Key':'regression-'+uuid4().hex}
original=client.post('/api/bulk-issue',headers=headers,json={'course_id':100})
assert original.status_code==200,original.text

def counts():
    with connect() as db:
        with db.cursor() as c:
            c.execute('SELECT (SELECT COUNT(*) FROM certificates) certificates,(SELECT COUNT(*) FROM audit_events) audits,(SELECT COUNT(*) FROM operations) operations')
            return c.fetchone()

before=counts()
expected_missing=int(sys.argv[1]) if len(sys.argv)>1 else 409
statuses={}
for course,expected in [(101,409),(999999,expected_missing)]:
    response=client.post('/api/bulk-issue',headers=headers,json={'course_id':course})
    statuses[str(course)]=response.status_code
    assert response.status_code==expected,response.text
    assert counts()==before,'Key misuse changed database state'
replay=client.post('/api/bulk-issue',headers=headers,json={'course_id':100})
assert replay.status_code==200 and replay.json()==original.json(),'Original result was changed'
for course in (999999,200):
    response=client.post('/api/bulk-issue',headers={**headers,'Idempotency-Key':uuid4().hex},json={'course_id':course})
    assert response.status_code==404,response.text
    assert counts()==before,'Rejected new operation changed database state'
print(json.dumps({'status':'PASS','replacement_course_statuses':statuses,'database_unchanged':True,
    'original_result_preserved':True,'unused_key_missing_or_foreign_course':404}))
