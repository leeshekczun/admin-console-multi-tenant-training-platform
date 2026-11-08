from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from backend.db import connect, initialize


def seed():
    initialize()
    with connect() as db:
        with db.cursor() as c:
            for tid, name, zone, email, base in [
                (1, 'East', 'Australia/Sydney', 'alice@east.test', 100),
                (2, 'West', 'Australia/Perth', 'bob@west.test', 200),
            ]:
                c.execute('INSERT IGNORE INTO tenants VALUES (%s,%s,%s)', (tid,name,zone))
                c.execute('INSERT IGNORE INTO admins VALUES (%s,%s,%s)', (tid,tid,email))
                c.execute('INSERT IGNORE INTO courses VALUES (%s,%s,%s)', (base,tid,'Safety 101'))
                c.execute('INSERT IGNORE INTO courses VALUES (%s,%s,%s)', (base+1,tid,'First Aid'))
                for n, learner, completed in [(1,'Alex Lee',1),(2,'Jamie Chen',0),(3,'Taylor Smith',1),(4,'Morgan Park',1)]:
                    c.execute('INSERT IGNORE INTO learners VALUES (%s,%s,%s)', (base+n,tid,learner))
                    c.execute('INSERT IGNORE INTO enrollments VALUES (%s,%s,%s,%s,%s)', (base+n,tid,base,base+n,completed))
                instant = datetime(2026,1,10,13,30,tzinfo=timezone.utc)
                c.execute('''INSERT IGNORE INTO certificates
                    (tenant_id,enrollment_id,serial_number,issued_at,issue_date)
                    VALUES (%s,%s,%s,%s,%s)''',
                    (tid,base+3,f'DEMO-{name.upper()}-001',instant.replace(tzinfo=None),instant.astimezone(ZoneInfo(zone)).date()))
                c.execute('SELECT id FROM certificates WHERE tenant_id=%s AND enrollment_id=%s',(tid,base+3))
                cert_id = c.fetchone()['id']
                c.execute('''INSERT IGNORE INTO audit_events
                    (tenant_id,certificate_id,actor_id,action,occurred_at) VALUES (%s,%s,%s,'ISSUED',%s)''',
                    (tid,cert_id,tid,instant.replace(tzinfo=None)))
        db.commit()


if __name__ == '__main__':
    seed()
    print('Schema and repeatable demo data ready.')
