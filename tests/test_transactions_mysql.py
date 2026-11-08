"""Fault injection and deterministic transaction interleavings against real MySQL.
Run explicitly with MYSQL_DATABASE=certificate_admin_test; never touches demo records.
"""
import os
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

import pymysql
from fastapi.testclient import TestClient
from backend import main
from backend.db import connect as real_connect

@unittest.skipUnless(os.getenv('MYSQL_DATABASE')=='certificate_admin_test','Requires explicit isolated MySQL test database')
class Transactions(unittest.TestCase):
    def setUp(self):
        self.fixture=int(time.time_ns()//1000)
        self.headers={'X-Actor':'alice@east.test','Idempotency-Key':uuid4().hex}
        with real_connect() as db:
            with db.cursor() as c:
                c.execute('INSERT INTO courses VALUES (%s,1,%s)',(self.fixture,'Transaction Test '+str(self.fixture)))
                for n in range(2):
                    lid=self.fixture+n
                    c.execute('INSERT INTO learners VALUES (%s,1,%s)',(lid,'Transaction Learner '+str(lid)))
                    c.execute('INSERT INTO enrollments VALUES (%s,1,%s,%s,1)',(lid,self.fixture,lid))
            db.commit()
    def issue(self):
        with TestClient(main.app,raise_server_exceptions=False) as client:
            return client.post('/api/bulk-issue',json={'course_id':self.fixture},headers=self.headers)
    def state(self):
        with real_connect() as db:
            with db.cursor() as c:
                c.execute('''SELECT (SELECT COUNT(*) FROM certificates c JOIN enrollments e ON e.id=c.enrollment_id WHERE e.course_id=%s) certificates,
                    (SELECT COUNT(*) FROM audit_events a JOIN certificates c ON c.id=a.certificate_id JOIN enrollments e ON e.id=c.enrollment_id WHERE e.course_id=%s) audits,
                    (SELECT COUNT(*) FROM operations WHERE idempotency_key=%s) operations''',(self.fixture,self.fixture,self.headers['Idempotency-Key']))
                return c.fetchone()
    def test_audit_integrity_failure_rolls_back_just_failed_learner(self):
        seen=[]
        def hook(cursor,query,params):
            if 'INSERT INTO audit_events' in query and not seen:
                with cursor.connection.cursor() as proof:
                    proof.execute('SELECT COUNT(*) n FROM certificates WHERE id=%s',(params[1],))
                    seen.append(proof.fetchone()['n'])
                raise pymysql.IntegrityError(1062,'injected audit failure after certificate insert')
        with patch.object(main,'connect',side_effect=lambda **kw:ConnectionProxy(real_connect(**kw),hook)):
            response=self.issue()
        self.assertEqual(seen,[1]); self.assertEqual(response.status_code,200)
        self.assertEqual([x['outcome'] for x in response.json()['outcomes']],['failed','issued'])
        self.assertEqual(self.state(),{'certificates':1,'audits':1,'operations':1})
    def test_second_audit_failure_rolls_back_entire_transaction(self):
        seen=[]
        def hook(cursor,query,params):
            if 'INSERT INTO audit_events' in query:
                seen.append(params[1])
                if len(seen)==2: raise pymysql.OperationalError(2013,'injected transaction failure')
        with patch.object(main,'connect',side_effect=lambda **kw:ConnectionProxy(real_connect(**kw),hook)):
            response=self.issue()
        self.assertEqual(len(seen),2); self.assertEqual(response.status_code,500)
        self.assertEqual(self.state(),{'certificates':0,'audits':0,'operations':0})
        # The same key is safe to retry after a full rollback.
        self.assertEqual(self.issue().status_code,200)
        self.assertEqual(self.state(),{'certificates':2,'audits':2,'operations':1})
    def test_revocation_audit_failure_rolls_back_status(self):
        result=self.issue().json(); cid=result['outcomes'][0]['certificate_id']
        def hook(cursor,query,params):
            if 'INSERT INTO audit_events' in query:
                with cursor.connection.cursor() as proof:
                    proof.execute('SELECT status FROM certificates WHERE id=%s',(cid,))
                    self.assertEqual(proof.fetchone()['status'],'REVOKED')
                raise pymysql.OperationalError(2013,'injected revocation audit failure')
        with patch.object(main,'connect',side_effect=lambda **kw:ConnectionProxy(real_connect(**kw),hook)):
            with TestClient(main.app,raise_server_exceptions=False) as client:
                response=client.post(f'/api/certificates/{cid}/revoke',headers=self.headers)
        self.assertEqual(response.status_code,500)
        with real_connect() as db:
            with db.cursor() as c:
                c.execute('SELECT status FROM certificates WHERE id=%s',(cid,)); self.assertEqual(c.fetchone()['status'],'ACTIVE')
                c.execute("SELECT COUNT(*) n FROM audit_events WHERE certificate_id=%s AND action='REVOKED'",(cid,)); self.assertEqual(c.fetchone()['n'],0)
    def test_uncommitted_issuance_invisible_and_retry_waits_for_commit(self):
        paused=threading.Event(); release=threading.Event(); second_entered=threading.Event(); second_acquired=threading.Event()
        guard=threading.Lock(); lock_calls=[0]; commit_calls=[0]
        def hook(cursor,query,params):
            if query=='SELECT id FROM tenants WHERE id=%s FOR UPDATE':
                with guard:
                    lock_calls[0]+=1; number=lock_calls[0]
                if number==2:
                    second_entered.set()
                    cursor.after_execute=lambda:second_acquired.set()
        def before_commit():
            with guard:
                commit_calls[0]+=1; number=commit_calls[0]
            if number==1:
                paused.set()
                if not release.wait(5): raise TimeoutError('Test did not release first transaction')
        with patch.object(main,'connect',side_effect=lambda **kw:ConnectionProxy(real_connect(**kw),hook,before_commit)):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first=pool.submit(self.issue)
                try:
                    self.assertTrue(paused.wait(3),'First request never reached pre-commit barrier')
                    self.assertEqual(self.state(),{'certificates':0,'audits':0,'operations':0})
                    second=pool.submit(self.issue)
                    self.assertTrue(second_entered.wait(3),'Second request never attempted tenant lock')
                    self.assertFalse(second_acquired.wait(.15),'Second transaction passed uncommitted lock')
                    self.assertFalse(second.done())
                finally: release.set()
                r1=first.result(timeout=5);r2=second.result(timeout=5)
        self.assertEqual(r1.status_code,200);self.assertEqual(r2.status_code,200)
        self.assertEqual(r1.json(),r2.json());self.assertTrue(second_acquired.is_set())
        self.assertEqual(self.state(),{'certificates':2,'audits':2,'operations':1})
    def test_forced_foreign_ids_leave_real_database_unchanged(self):
        original=self.issue().json();cid=original['outcomes'][0]['certificate_id'];before=self.state()
        with TestClient(main.app) as client:
            bob={'X-Actor':'bob@west.test','Idempotency-Key':uuid4().hex}
            self.assertEqual(client.get(f'/api/certificates/{cid}',headers=bob).status_code,404)
            self.assertEqual(client.post(f'/api/certificates/{cid}/revoke',headers=bob).status_code,404)
            self.assertEqual(client.post('/api/bulk-issue',headers=bob,json={'course_id':self.fixture}).status_code,404)
            self.assertEqual(client.get('/api/certificates',headers=bob,params={'search':'Transaction Learner'}).json()['total'],0)
            text=client.get('/api/certificates/export',headers=bob,params={'search':'Transaction Learner'}).text
            self.assertEqual(len(text.splitlines()),1)
        self.assertEqual(self.state(),before)

class ConnectionProxy:
    def __init__(self,connection,hook,before_commit=None):
        self.connection=connection;self.hook=hook;self.before_commit=before_commit
    def __enter__(self): self.connection.__enter__();return self
    def __exit__(self,*args):return self.connection.__exit__(*args)
    def cursor(self,*args,**kwargs):return CursorProxy(self.connection.cursor(*args,**kwargs),self.hook)
    def commit(self):
        if self.before_commit:self.before_commit()
        return self.connection.commit()

class CursorProxy:
    def __init__(self,cursor,hook):self.cursor=cursor;self.hook=hook;self.after_execute=None
    def __enter__(self):self.cursor.__enter__();return self
    def __exit__(self,*args):return self.cursor.__exit__(*args)
    def __getattr__(self,name):return getattr(self.cursor,name)
    def execute(self,query,params=None):
        self.hook(self.cursor,query,params) if not query.endswith('FOR UPDATE') else self.hook(self,query,params)
        result=self.cursor.execute(query,params)
        if self.after_execute:self.after_execute();self.after_execute=None
        return result

if __name__=='__main__':unittest.main(verbosity=2)
