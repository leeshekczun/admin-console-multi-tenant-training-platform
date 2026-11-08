"""Database-free API unit tests; transaction semantics are tested separately on MySQL."""
import copy
import json
import unittest
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from backend import main

ALICE={'id':1,'tenant_id':1,'email':'alice@east.test','timezone':'Australia/Sydney'}
BOB={**ALICE,'id':2,'tenant_id':2,'email':'bob@west.test','timezone':'Australia/Perth'}
ROW={'id':1,'serial_number':'S-001','issued_at':datetime(2026,1,10,13,30),'issue_date':date(2026,1,11),'status':'ACTIVE','learner_name':'Alex, "Lee"','course_title':'Safety 101'}

class ApiUnits(unittest.TestCase):
    def setUp(self):
        self.db=MagicMock(); self.db.__enter__.return_value=self.db
        self.c=self.db.cursor.return_value.__enter__.return_value
        self.patch=patch.object(main,'connect',return_value=self.db); self.patch.start()
        main.app.dependency_overrides[main.actor]=lambda:ALICE
        self.client=TestClient(main.app,raise_server_exceptions=False)
    def tearDown(self):
        main.app.dependency_overrides.clear(); self.patch.stop()
    def test_health_and_actor_choices(self):
        self.c.fetchone.return_value={'n':2,'db':'test'}
        self.assertEqual(self.client.get('/api/health').json()['database'],'test')
        self.c.fetchall.return_value=[{'email':'alice@east.test','tenant':'East'}]
        self.assertEqual(len(self.client.get('/api/actors').json()),1)
    def test_courses_are_tenant_scoped(self):
        self.c.fetchall.return_value=[{'id':100,'title':'Safety 101'}]
        self.assertEqual(self.client.get('/api/courses').json()[0]['id'],100)
        self.assertEqual(self.c.execute.call_args.args[1],(1,))
    def test_missing_and_unknown_identity(self):
        main.app.dependency_overrides.clear(); self.c.fetchone.return_value=None
        for headers in ({},{'X-Actor':'nobody@example.test'}):
            with self.subTest(headers=headers): self.assertEqual(self.client.get('/api/certificates',headers=headers).status_code,401)
    def test_illegal_query_parameters(self):
        for params in ({'page':0},{'page':-1},{'page_size':0},{'page_size':101},{'sort':'id; DROP TABLE certificates'},{'direction':'sideways'},{'search':'x'*161}):
            with self.subTest(params=params): self.assertEqual(self.client.get('/api/certificates',params=params).status_code,422)
    def test_illegal_issue_payloads_and_keys(self):
        for payload in ({},{'course_id':0},{'course_id':-1},{'course_id':'bad'},{'course_id':100,'tenant_id':2}):
            with self.subTest(payload=payload): self.assertEqual(self.client.post('/api/bulk-issue',json=payload,headers={'Idempotency-Key':'k'}).status_code,422)
        for headers in ({},{'Idempotency-Key':''},{'Idempotency-Key':'k'*129}):
            with self.subTest(headers=headers): self.assertEqual(self.client.post('/api/bulk-issue',json={'course_id':100},headers=headers).status_code,422)
        self.db.commit.assert_not_called()
    def test_list_search_pagination_sort_and_dst(self):
        self.c.fetchone.return_value={'total':21}; self.c.fetchall.return_value=[copy.deepcopy(ROW)]
        r=self.client.get('/api/certificates',params={'search':'Alex','page':2,'page_size':10,'sort':'issue_date','direction':'asc'})
        self.assertEqual(r.status_code,200); self.assertEqual(r.json()['items'][0]['issued_local'],'2026-01-11 00:30')
        query,params=self.c.execute.call_args.args
        self.assertIn('c.tenant_id=%s',query); self.assertIn('ORDER BY c.issue_date asc, c.id ASC',query)
        self.assertEqual(params,(1,'Alex','Alex',10,10)); self.assertEqual(r.json()['total'],21)
    def test_all_sort_fields_are_allowlisted_and_stable(self):
        for field in main.SORTS:
            for direction in ('asc','desc'):
                with self.subTest(field=field,direction=direction):
                    where,params,order=main.query_parts(BOB,'x',field,direction)
                    self.assertIn('c.tenant_id=%s',where); self.assertEqual(params,(2,'x','x')); self.assertTrue(order.endswith('c.id ASC'))
    def test_empty_list(self):
        self.c.fetchone.return_value={'total':0}; self.c.fetchall.return_value=[]
        self.assertEqual(self.client.get('/api/certificates').json()['items'],[])
    def test_detail_and_audit(self):
        self.c.fetchone.return_value=copy.deepcopy(ROW)
        self.c.fetchall.return_value=[{'action':'ISSUED','occurred_at':datetime(2026,1,10,13,30),'actor':'alice@east.test'}]
        r=self.client.get('/api/certificates/1'); self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['audit_events'][0]['occurred_at'],'2026-01-10T13:30:00+00:00')
    def test_forced_cross_tenant_detail_revoke_and_issue(self):
        main.app.dependency_overrides[main.actor]=lambda:BOB
        self.c.fetchone.return_value=None
        for method,path,kwargs in [('get','/api/certificates/1',{}),('post','/api/certificates/1/revoke',{}),('post','/api/bulk-issue',{'json':{'course_id':100},'headers':{'Idempotency-Key':'new'}})]:
            self.c.reset_mock()
            with self.subTest(path=path):
                self.assertEqual(getattr(self.client,method)(path,**kwargs).status_code,404)
                calls=self.c.execute.call_args_list
                self.assertTrue(any('tenant_id=%s' in call.args[0] and 2 in call.args[1] for call in calls))
        self.db.commit.assert_not_called()
    def test_bulk_mixed_outcomes_commit_and_audit(self):
        self.c.fetchone.side_effect=[None,{'id':100},None,None,{'id':9}]
        self.c.fetchall.return_value=[{'id':101,'learner_id':101,'completed':True,'name':'Alex'},{'id':102,'learner_id':102,'completed':False,'name':'Jamie'},{'id':103,'learner_id':103,'completed':True,'name':'Taylor'}]
        self.c.lastrowid=7
        r=self.client.post('/api/bulk-issue',json={'course_id':100},headers={'Idempotency-Key':'new'})
        self.assertEqual(r.status_code,200); self.assertEqual([x['outcome'] for x in r.json()['outcomes']],['issued','skipped','skipped'])
        self.assertEqual(sum('INSERT INTO audit_events' in x.args[0] for x in self.c.execute.call_args_list),1)
        self.db.commit.assert_called_once()
    def test_same_key_replays_saved_result_without_writes(self):
        payload=main.IssueRequest(course_id=100)
        fingerprint=main.hashlib.sha256(json.dumps(payload.model_dump(),sort_keys=True).encode()).hexdigest()
        result={'operation_id':7,'status':'COMPLETED','outcomes':[]}
        self.c.fetchone.return_value={'fingerprint':fingerprint,'result':json.dumps(result)}
        self.assertEqual(self.client.post('/api/bulk-issue',json={'course_id':100},headers={'Idempotency-Key':'same'}).json(),result)
        self.db.commit.assert_not_called()
        self.assertFalse(any('INSERT' in x.args[0] for x in self.c.execute.call_args_list))
    def test_same_key_changed_missing_course_conflicts_before_lookup(self):
        self.c.fetchone.return_value={'fingerprint':'different','result':'{}'}
        r=self.client.post('/api/bulk-issue',json={'course_id':999999},headers={'Idempotency-Key':'same'})
        self.assertEqual(r.status_code,409); self.db.commit.assert_not_called()
        self.assertFalse(any('FROM courses' in x.args[0] for x in self.c.execute.call_args_list))
    def test_revocation_first_and_repeat(self):
        for status,changed in [('ACTIVE',True),('REVOKED',False)]:
            with self.subTest(status=status):
                self.c.reset_mock(); self.db.commit.reset_mock(); self.c.fetchone.return_value={'status':status}
                r=self.client.post('/api/certificates/1/revoke')
                self.assertEqual(r.json()['changed'],changed); self.db.commit.assert_called_once()
                self.assertEqual(sum('INSERT INTO audit_events' in x.args[0] for x in self.c.execute.call_args_list),int(changed))
    def test_export_uses_search_sort_local_date_and_csv_escaping(self):
        self.c.fetchmany.side_effect=[[copy.deepcopy(ROW)],[]]
        r=self.client.get('/api/certificates/export',params={'search':'Alex','sort':'learner_name','direction':'desc'})
        self.assertEqual(r.status_code,200); self.assertIn('"Alex, ""Lee"""',r.text); self.assertIn('2026-01-11',r.text)
        self.assertEqual(self.c.execute.call_args.args[1],(1,'Alex','Alex'))
        self.assertIn('ORDER BY l.name desc, c.id ASC',self.c.execute.call_args.args[0])
        self.c.fetchmany.assert_called_with(1000)
    def test_west_dst(self):
        row=copy.deepcopy(ROW);row['issue_date']=date(2026,1,10)
        self.assertEqual(main.display(row,BOB)['issued_local'],'2026-01-10 21:30')
    def test_database_failure_is_not_success(self):
        self.c.execute.side_effect=RuntimeError('injected database failure')
        self.assertEqual(self.client.get('/api/certificates').status_code,500); self.db.commit.assert_not_called()

if __name__=='__main__': unittest.main(verbosity=2)
