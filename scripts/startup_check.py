"""Bounded frontend -> API -> database check with isolated, retained check records."""
import json
import os
import signal
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import httpx
from backend.db import connect

BASE=os.getenv('BASE_URL','http://127.0.0.1:8010')
STEP='configuration'


def run():
    global STEP
    started=time.monotonic()
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('45 second total timeout')))
    signal.alarm(45)
    try:
        STEP='database configuration and required tables'
        with connect() as db:
            with db.cursor() as c:
                for table in ('tenants','admins','courses','learners','enrollments','certificates','operations','audit_events'):
                    c.execute(f'SELECT 1 FROM {table} LIMIT 1')
        with httpx.Client(base_url=BASE,timeout=10,headers={'X-Actor':'alice@east.test'}) as client:
            STEP='frontend and service readiness'
            response=client.get('/'); response.raise_for_status()
            assert '<div id="app">' in response.text,'Built frontend missing'
            health=client.get('/api/health'); health.raise_for_status()
            STEP='isolated check fixture'
            fixture=int(time.time_ns()//1000)
            name='Startup Check '+uuid4().hex[:12]
            with connect() as db:
                with db.cursor() as c:
                    c.execute('INSERT INTO courses VALUES (%s,1,%s)',(fixture,name))
                    c.execute('INSERT INTO learners VALUES (%s,1,%s)',(fixture,name))
                    c.execute('INSERT INTO enrollments VALUES (%s,1,%s,%s,1)',(fixture,fixture,fixture))
                db.commit()
            STEP='API issuance and readback'
            response=client.post('/api/bulk-issue',json={'course_id':fixture},headers={'Idempotency-Key':'startup-'+uuid4().hex})
            response.raise_for_status(); result=response.json()
            assert result['outcomes'][0]['outcome']=='issued',result
            cid=result['outcomes'][0]['certificate_id']
            detail=client.get('/api/certificates/'+str(cid)); detail.raise_for_status()
            assert detail.json()['learner_name']==name
            listed=client.get('/api/certificates',params={'search':name}); listed.raise_for_status()
            assert listed.json()['total']==1
            STEP='database certificate and exact audit count'
            with connect() as db:
                with db.cursor() as c:
                    c.execute("SELECT COUNT(*) n FROM audit_events WHERE certificate_id=%s AND action='ISSUED'",(cid,))
                    assert c.fetchone()['n']==1
            print(json.dumps({'status':'PASS','elapsed_seconds':round(time.monotonic()-started,3),
                              'base_url':BASE,'isolated_fixture':name,'certificate_id':cid}))
    finally:
        signal.alarm(0)


if __name__=='__main__':
    try: run()
    except Exception as exc:
        print(f'FAIL at {STEP}: {exc}',file=sys.stderr)
        sys.exit(1)
