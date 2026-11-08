"""Add 100,000 East certificates on explicit invocation; never part of quick-start seed."""
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from backend.db import connect, initialize

COURSE=900000000
BASE=10000000


def generate(count=100000):
    initialize()
    started=time.monotonic()
    with connect() as db:
        with db.cursor() as c:
            c.execute('SELECT id FROM tenants WHERE id=1 FOR UPDATE')
            c.execute("INSERT IGNORE INTO courses VALUES (%s,1,'Export Growth Dataset')",(COURSE,))
            for offset in range(0,count,2000):
                indexes=range(offset,min(offset+2000,count))
                # Ten identical learner names per group deliberately exercise stable sort ties.
                c.executemany('INSERT IGNORE INTO learners VALUES (%s,1,%s)',
                              [(BASE+i,f'Growth Learner {i//10:05d}') for i in indexes])
                c.executemany('INSERT IGNORE INTO enrollments VALUES (%s,1,%s,%s,1)',
                              [(BASE+i,COURSE,BASE+i) for i in indexes])
                c.executemany('''INSERT IGNORE INTO certificates
                    (tenant_id,enrollment_id,serial_number,issued_at,issue_date)
                    VALUES (1,%s,%s,%s,%s)''',
                    [(BASE+i,f'GROWTH-EAST-{i:06d}',datetime(2026,1,10,13,30),'2026-01-11') for i in indexes])
            c.execute('''INSERT IGNORE INTO audit_events
                (tenant_id,certificate_id,actor_id,action,occurred_at)
                SELECT 1,c.id,1,'ISSUED',c.issued_at FROM certificates c
                JOIN enrollments e ON e.id=c.enrollment_id AND e.tenant_id=c.tenant_id
                WHERE c.tenant_id=1 AND e.course_id=%s''',(COURSE,))
        db.commit()
    print(f'Growth dataset ready: {count} East certificates, {time.monotonic()-started:.3f}s, database={os.getenv("MYSQL_DATABASE","certificate_admin")}')


if __name__=='__main__': generate()
