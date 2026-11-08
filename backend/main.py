import csv
import hashlib
import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pymysql
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from backend.db import connect

app = FastAPI(title='Certificate Admin', version='1.0.0')
log = logging.getLogger('uvicorn.error')


def actor(x_actor: str = Header(default='')):
    with connect() as db:
        with db.cursor() as c:
            c.execute('''SELECT a.id, a.tenant_id, a.email, t.name tenant, t.timezone
                FROM admins a JOIN tenants t ON t.id=a.tenant_id WHERE a.email=%s''', (x_actor,))
            result = c.fetchone()
    if not result:
        raise HTTPException(401, 'A valid X-Actor demo administrator is required.')
    return result


@app.get('/api/health')
def health():
    with connect() as db:
        with db.cursor() as c:
            c.execute('SELECT COUNT(*) n, DATABASE() db FROM tenants')
            row=c.fetchone()
            return {'status': 'ready', 'tenants': row['n'], 'database':row['db']}


@app.get('/api/actors')
def actors():
    # Public demo identities are explicitly seeded; this endpoint is not authentication.
    with connect() as db:
        with db.cursor() as c:
            c.execute('SELECT a.email, t.name tenant FROM admins a JOIN tenants t ON t.id=a.tenant_id ORDER BY a.id')
            return c.fetchall()


@app.get('/api/courses')
def courses(a=Depends(actor)):
    with connect() as db:
        with db.cursor() as c:
            c.execute('SELECT id,title FROM courses WHERE tenant_id=%s ORDER BY id', (a['tenant_id'],))
            return c.fetchall()


SELECT = '''SELECT c.id,c.serial_number,c.issued_at,c.issue_date,c.status,
    l.name learner_name, co.title course_title
    FROM certificates c JOIN enrollments e ON e.id=c.enrollment_id AND e.tenant_id=c.tenant_id
    JOIN learners l ON l.id=e.learner_id AND l.tenant_id=e.tenant_id
    JOIN courses co ON co.id=e.course_id AND co.tenant_id=e.tenant_id'''
SORTS = {'learner_name':'l.name', 'course_title':'co.title', 'serial_number':'c.serial_number',
         'issue_date':'c.issue_date', 'status':'c.status'}


def query_parts(a, search, sort, direction):
    if sort not in SORTS or direction not in ('asc', 'desc'):
        raise HTTPException(422, 'Invalid sort field or direction.')
    where = ' WHERE c.tenant_id=%s AND (LOCATE(%s,l.name)>0 OR LOCATE(%s,c.serial_number)>0)'
    order = f' ORDER BY {SORTS[sort]} {direction}, c.id ASC'
    return where, (a['tenant_id'], search, search), order


def display(row, a):
    row['issued_at'] = row['issued_at'].replace(tzinfo=timezone.utc).isoformat().replace('+00:00','Z')
    row['issued_local'] = datetime.fromisoformat(row['issued_at']).astimezone(ZoneInfo(a['timezone'])).strftime('%Y-%m-%d %H:%M')
    row['issue_date'] = row['issue_date'].isoformat()
    row['timezone'] = a['timezone']
    return row


@app.get('/api/certificates')
def certificates(search: str = Query('',max_length=160), sort: str = 'issue_date', direction: str = 'desc',
                 page: int = Query(1,ge=1), page_size: int = Query(20,ge=1,le=100), a=Depends(actor)):
    where, params, order = query_parts(a,search,sort,direction)
    with connect() as db:
        with db.cursor() as c:
            c.execute('SELECT COUNT(*) total FROM ('+SELECT+where+') matching', params)
            total=c.fetchone()['total']
            c.execute(SELECT+where+order+' LIMIT %s OFFSET %s', (*params,page_size,(page-1)*page_size))
            rows=[display(r,a) for r in c.fetchall()]
    return {'items':rows,'total':total,'page':page,'page_size':page_size}


@app.get('/api/certificates/export')
def export(search: str = Query('',max_length=160), sort: str = 'issue_date', direction: str = 'desc', a=Depends(actor)):
    where, params, order = query_parts(a,search,sort,direction)

    def stream():
        # Server-side cursor bounds memory; this connection belongs only to the export.
        with connect(cursorclass=pymysql.cursors.SSDictCursor) as db:
            with db.cursor() as c:
                c.execute(SELECT+where+order,params)
                buf=io.StringIO()
                writer=csv.writer(buf)
                writer.writerow(['learner_name','course_title','serial_number','issue_date'])
                yield buf.getvalue()
                while True:
                    rows=c.fetchmany(1000)
                    if not rows:
                        break
                    buf.seek(0); buf.truncate(0)
                    for r in rows:
                        writer.writerow([r['learner_name'],r['course_title'],r['serial_number'],r['issue_date'].isoformat()])
                    yield buf.getvalue()
    return StreamingResponse(stream(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="certificates.csv"'})


@app.get('/api/certificates/{certificate_id}')
def detail(certificate_id: int, a=Depends(actor)):
    with connect() as db:
        with db.cursor() as c:
            c.execute(SELECT+' WHERE c.id=%s AND c.tenant_id=%s',(certificate_id,a['tenant_id']))
            row=c.fetchone()
            if not row:
                raise HTTPException(404,'Certificate not found.')
            c.execute('''SELECT action,occurred_at,a.email actor FROM audit_events ev
                JOIN admins a ON a.id=ev.actor_id AND a.tenant_id=ev.tenant_id
                WHERE ev.certificate_id=%s AND ev.tenant_id=%s ORDER BY ev.id''',(certificate_id,a['tenant_id']))
            events=c.fetchall()
            for event in events:
                event['occurred_at']=event['occurred_at'].replace(tzinfo=timezone.utc).isoformat()
            return {**display(row,a),'audit_events':events}


class IssueRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    course_id: int = Field(gt=0)


@app.post('/api/bulk-issue')
def bulk_issue(payload: IssueRequest, idempotency_key: str = Header(min_length=1,max_length=128), a=Depends(actor)):
    fingerprint=hashlib.sha256(json.dumps(payload.model_dump(),sort_keys=True).encode()).hexdigest()
    with connect() as db:
        with db.cursor() as c:
            # A tenant row lock serializes operations within this small admin console.
            # It works across processes, keeps retries waiting for the committed result,
            # and also protects different-key requests from duplicate issuance races.
            c.execute('SELECT id FROM tenants WHERE id=%s FOR UPDATE',(a['tenant_id'],))
            c.execute('SELECT id FROM courses WHERE id=%s AND tenant_id=%s',(payload.course_id,a['tenant_id']))
            if not c.fetchone():
                raise HTTPException(404,'Course not found.')
            c.execute('''SELECT * FROM operations WHERE tenant_id=%s AND actor_id=%s AND idempotency_key=%s''',
                      (a['tenant_id'],a['id'],idempotency_key))
            previous=c.fetchone()
            if previous:
                if previous['fingerprint'] != fingerprint:
                    raise HTTPException(409,'Idempotency key was used for a different request.')
                return json.loads(previous['result'])
            c.execute('''INSERT INTO operations (tenant_id,actor_id,idempotency_key,fingerprint,status)
                VALUES (%s,%s,%s,%s,'RUNNING')''',(a['tenant_id'],a['id'],idempotency_key,fingerprint))
            operation_id=c.lastrowid
            c.execute('''SELECT e.id,e.learner_id,e.completed,l.name FROM enrollments e
                JOIN learners l ON l.id=e.learner_id AND l.tenant_id=e.tenant_id
                WHERE e.tenant_id=%s AND e.course_id=%s ORDER BY e.id''',(a['tenant_id'],payload.course_id))
            learners=c.fetchall()
            outcomes=[]
            for learner in learners:
                item={'learner_id':learner['learner_id'],'learner_name':learner['name']}
                c.execute('SELECT id FROM certificates WHERE tenant_id=%s AND enrollment_id=%s',(a['tenant_id'],learner['id']))
                existing=c.fetchone()
                if existing:
                    outcomes.append({**item,'outcome':'skipped','reason':'already_certified'})
                    continue
                if not learner['completed']:
                    outcomes.append({**item,'outcome':'skipped','reason':'incomplete'})
                    continue
                now=datetime.now(timezone.utc)
                serial='CERT-'+uuid4().hex.upper()
                c.execute('SAVEPOINT learner_issue')
                try:
                    c.execute('''INSERT INTO certificates
                        (tenant_id,enrollment_id,serial_number,issued_at,issue_date) VALUES (%s,%s,%s,%s,%s)''',
                        (a['tenant_id'],learner['id'],serial,now.replace(tzinfo=None),now.astimezone(ZoneInfo(a['timezone'])).date()))
                    cert_id=c.lastrowid
                    c.execute('''INSERT INTO audit_events (tenant_id,certificate_id,actor_id,action,occurred_at)
                        VALUES (%s,%s,%s,'ISSUED',%s)''',(a['tenant_id'],cert_id,a['id'],now.replace(tzinfo=None)))
                    outcomes.append({**item,'outcome':'issued','certificate_id':cert_id,'serial_number':serial})
                except pymysql.IntegrityError:
                    c.execute('ROLLBACK TO SAVEPOINT learner_issue')
                    log.exception('Issuance integrity failure for enrollment %s',learner['id'])
                    outcomes.append({**item,'outcome':'failed','reason':'issuance_constraint_failure'})
                c.execute('RELEASE SAVEPOINT learner_issue')
            result={'operation_id':operation_id,'status':'COMPLETED','outcomes':outcomes}
            c.execute('UPDATE operations SET status=%s,result=%s WHERE id=%s',('COMPLETED',json.dumps(result),operation_id))
        db.commit()
        return result


@app.post('/api/certificates/{certificate_id}/revoke')
def revoke(certificate_id: int, a=Depends(actor)):
    with connect() as db:
        with db.cursor() as c:
            c.execute('SELECT status FROM certificates WHERE id=%s AND tenant_id=%s FOR UPDATE',(certificate_id,a['tenant_id']))
            row=c.fetchone()
            if not row:
                raise HTTPException(404,'Certificate not found.')
            changed=row['status'] != 'REVOKED'
            if changed:
                now=datetime.now(timezone.utc).replace(tzinfo=None)
                c.execute("UPDATE certificates SET status='REVOKED',revoked_at=%s WHERE id=%s AND tenant_id=%s",(now,certificate_id,a['tenant_id']))
                c.execute('''INSERT INTO audit_events (tenant_id,certificate_id,actor_id,action,occurred_at)
                    VALUES (%s,%s,%s,'REVOKED',%s)''',(a['tenant_id'],certificate_id,a['id'],now))
        db.commit()
    return {'id':certificate_id,'status':'REVOKED','changed':changed}


dist=Path(__file__).resolve().parent.parent/'frontend'/'dist'
if dist.exists():
    app.mount('/',StaticFiles(directory=dist,html=True),name='frontend')
