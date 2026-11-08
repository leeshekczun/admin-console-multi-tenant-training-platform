"""Direct API and SQL evidence for A1-A7. Run against the isolated test database/server."""
import csv
import io
import json
import os
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import httpx
from backend.db import connect
from scripts.generate_100k import generate

BASE=os.getenv('BASE_URL','http://127.0.0.1:8011')
ALICE={'X-Actor':'alice@east.test'}
BOB={'X-Actor':'bob@west.test'}
results=[]


def sql(statement,params=()):
    with connect() as db:
        with db.cursor() as c:
            c.execute(statement,params)
            return c.fetchall()


def request(method,path,headers=ALICE,**kwargs):
    with httpx.Client(base_url=BASE,timeout=60) as client:
        return client.request(method,path,headers=headers,**kwargs)


def record(name,evidence):
    results.append({'scenario':name,'status':'PASS','evidence':evidence})
    print('PASS',name,json.dumps(evidence),flush=True)


def main():
    if os.getenv('MYSQL_DATABASE') != 'certificate_admin_test':
        raise RuntimeError('Use MYSQL_DATABASE=certificate_admin_test and a matching isolated server.')
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('180-second suite timeout')))
    signal.alarm(180)
    fixture=int(time.time_ns()//1000)
    with connect() as db:
        with db.cursor() as c:
            c.execute('INSERT INTO courses VALUES (%s,1,%s)',(fixture,'Acceptance '+str(fixture)))
            for i,done in enumerate([1,0,1,1]):
                lid=fixture+i
                c.execute('INSERT INTO learners VALUES (%s,1,%s)',(lid,'Acceptance Learner '+str(i)))
                c.execute('INSERT INTO enrollments VALUES (%s,1,%s,%s,%s)',(lid,fixture,lid,done))
            c.execute('''INSERT INTO certificates (tenant_id,enrollment_id,serial_number,issued_at,issue_date)
                VALUES (1,%s,%s,'2026-01-10 13:30:00','2026-01-11')''',(fixture+2,'ACCEPT-'+uuid4().hex))
            c.execute('''INSERT INTO audit_events (tenant_id,certificate_id,actor_id,action,occurred_at)
                VALUES (1,%s,1,'ISSUED','2026-01-10 13:30:00')''',(c.lastrowid,))
        db.commit()

    east_id=sql("SELECT id FROM certificates WHERE serial_number='DEMO-EAST-001'")[0]['id']
    before=sql('SELECT (SELECT COUNT(*) FROM certificates) certs,(SELECT COUNT(*) FROM audit_events) audits,(SELECT COUNT(*) FROM operations) ops')
    for path in [f'/api/certificates/{east_id}',f'/api/certificates/{east_id}/revoke']:
        method='POST' if path.endswith('revoke') else 'GET'
        assert request(method,path,BOB).status_code==404
    assert request('POST','/api/bulk-issue',{**BOB,'Idempotency-Key':uuid4().hex},json={'course_id':100}).status_code==404
    response=request('GET','/api/certificates',BOB,params={'search':'DEMO-EAST'})
    assert response.status_code==200 and response.json()['total']==0
    response=request('GET','/api/certificates/export',BOB,params={'search':'DEMO-EAST'})
    assert response.status_code==200 and len(list(csv.reader(io.StringIO(response.text))))==1
    assert before==sql('SELECT (SELECT COUNT(*) FROM certificates) certs,(SELECT COUNT(*) FROM audit_events) audits,(SELECT COUNT(*) FROM operations) ops')
    assert request('GET','/api/certificates',{}).status_code==401
    record('A1',{'cross_tenant_detail_revoke_issue':404,'west_list_export_east_matches':0,'database_unchanged':True,'missing_actor':401})

    key=uuid4().hex
    headers={**ALICE,'Idempotency-Key':key}
    def issue(_=None):
        response=request('POST','/api/bulk-issue',headers,json={'course_id':fixture})
        assert response.status_code==200,response.text
        return response.json()
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes=list(pool.map(issue,range(8)))
    expected=outcomes[0]
    assert all(x==expected for x in outcomes)
    assert issue()==expected and issue()==expected
    counts=sql('''SELECT c.id,COUNT(a.id) n FROM certificates c
        JOIN enrollments e ON e.id=c.enrollment_id AND e.tenant_id=c.tenant_id
        LEFT JOIN audit_events a ON a.certificate_id=c.id AND a.action='ISSUED'
        WHERE e.course_id=%s GROUP BY c.id''',(fixture,))
    assert len(counts)==3 and all(x['n']==1 for x in counts),counts
    assert sql('SELECT COUNT(*) n FROM operations WHERE tenant_id=1 AND idempotency_key=%s',(key,))[0]['n']==1
    record('A2',{'concurrent_callers':8,'sequential_retries':2,'operation_id':expected['operation_id'],'same_results':True,'certificates':3,'one_issuance_audit_each':True})

    counts_before=sql('SELECT (SELECT COUNT(*) FROM certificates) certs,(SELECT COUNT(*) FROM audit_events) audits,(SELECT COUNT(*) FROM operations) ops')
    response=request('POST','/api/bulk-issue',headers,json={'course_id':101})
    assert response.status_code==409,response.text
    assert counts_before==sql('SELECT (SELECT COUNT(*) FROM certificates) certs,(SELECT COUNT(*) FROM audit_events) audits,(SELECT COUNT(*) FROM operations) ops')
    assert issue()==expected
    record('A3',{'different_course':409,'database_unchanged':True,'original_result_preserved':True})

    per_learner={x['learner_id']-fixture:x for x in expected['outcomes']}
    assert per_learner[0]['outcome']=='issued' and per_learner[3]['outcome']=='issued'
    assert per_learner[1]['reason']=='incomplete' and per_learner[2]['reason']=='already_certified'
    record('A4',{'outcomes':expected['outcomes']})

    for headers,serial,local,date in [(ALICE,'DEMO-EAST-001','2026-01-11 00:30','2026-01-11'),(BOB,'DEMO-WEST-001','2026-01-10 21:30','2026-01-10')]:
        response=request('GET','/api/certificates',headers,params={'search':serial,'sort':'issue_date','direction':'asc'})
        assert response.status_code==200
        row=response.json()['items'][0]
        assert row['issued_local']==local and row['issue_date']==date and row['issued_at']=='2026-01-10T13:30:00Z',row
        detail=request('GET',f"/api/certificates/{row['id']}",headers).json()
        assert detail['issued_local']==local
        exported=list(csv.DictReader(io.StringIO(request('GET','/api/certificates/export',headers,params={'search':serial}).text)))
        assert exported[0]['issue_date']==date
    record('A5',{'east':'2026-01-11 00:30','west':'2026-01-10 21:30','csv_local_dates':True})

    cid=per_learner[0]['certificate_id']
    with ThreadPoolExecutor(max_workers=4) as pool:
        revokes=list(pool.map(lambda _:request('POST',f'/api/certificates/{cid}/revoke').json(),range(4)))
    assert sum(x['changed'] for x in revokes)==1,revokes
    assert request('POST',f'/api/certificates/{cid}/revoke').json()['changed'] is False
    assert sql("SELECT COUNT(*) n FROM audit_events WHERE certificate_id=%s AND action='REVOKED'",(cid,))[0]['n']==1
    another=request('POST','/api/bulk-issue',{**ALICE,'Idempotency-Key':uuid4().hex},json={'course_id':fixture}).json()
    assert all(x['outcome']=='skipped' for x in another['outcomes']),another
    record('A7',{'concurrent_revokes':4,'changes':1,'revocation_audits':1,'revoked_reissue':'skipped'})

    generate()
    # Seed repeatability is checked independently of generation and issuance changes.
    before=sql('SELECT (SELECT COUNT(*) FROM certificates) certs,(SELECT COUNT(*) FROM audit_events) audits')
    from backend.seed import seed
    seed(); seed(); generate()
    assert before==sql('SELECT (SELECT COUNT(*) FROM certificates) certs,(SELECT COUNT(*) FROM audit_events) audits')
    params={'search':'Growth Learner','sort':'learner_name','direction':'desc'}
    first_chunk=threading.Event(); list_done=threading.Event()
    def first_export():
        start=time.monotonic()
        parts=[]
        with httpx.Client(base_url=BASE,timeout=60) as client:
            with client.stream('GET','/api/certificates/export',headers=ALICE,params=params) as response:
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    parts.append(chunk)
                    if not first_chunk.is_set():
                        first_chunk.set()
                        assert list_done.wait(10),'Concurrent list never completed'
        return b''.join(parts),time.monotonic()-start
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(first_export)
        assert first_chunk.wait(20),'Export did not start'
        assert not future.done(),'Export must still be active'
        list_start=time.monotonic()
        response=request('GET','/api/certificates',params={**params,'page_size':10})
        list_seconds=time.monotonic()-list_start
        list_done.set()
        assert response.status_code==200 and response.json()['total']==100000,response.text
        data1,seconds1=future.result(timeout=60)
    start=time.monotonic()
    response2=request('GET','/api/certificates/export',params=params)
    seconds2=time.monotonic()-start
    assert response2.status_code==200
    data2=response2.content
    assert seconds1<60 and seconds2<60
    assert data1==data2,'Repeated export ordering differs'
    rows=list(csv.DictReader(io.StringIO(data1.decode())))
    expected_rows=sql('''SELECT l.name learner_name,co.title course_title,c.serial_number,c.issue_date
        FROM certificates c JOIN enrollments e ON e.id=c.enrollment_id AND e.tenant_id=c.tenant_id
        JOIN learners l ON l.id=e.learner_id AND l.tenant_id=e.tenant_id
        JOIN courses co ON co.id=e.course_id AND co.tenant_id=e.tenant_id
        WHERE c.tenant_id=1 AND LOCATE('Growth Learner',l.name)>0 ORDER BY l.name DESC,c.id ASC''')
    for x in expected_rows: x['issue_date']=x['issue_date'].isoformat()
    assert len(rows)==100000 and rows==expected_rows,'CSV does not match exact tenant/search/order'
    record('A6',{'matching_rows':len(rows),'first_export_seconds':round(seconds1,3),'second_export_seconds':round(seconds2,3),
                 'list_during_export_seconds':round(list_seconds,3),'exact_sql_match':True,'repeat_bytes_identical':True,'seed_generator_repeatable':True})
    signal.alarm(0)


if __name__=='__main__':
    started=time.time()
    failure=None
    try: main()
    except Exception as exc:
        failure=str(exc)
        results.append({'scenario':'suite','status':'FAIL','error':repr(exc)})
        import traceback
        traceback.print_exc()
    finally:
        Path('verification/acceptance.json').write_text(json.dumps({'started_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(started)),
            'database':os.getenv('MYSQL_DATABASE'),'base_url':BASE,'elapsed_seconds':round(time.time()-started,3),'results':results},indent=2))
    if failure is not None: sys.exit(1)
