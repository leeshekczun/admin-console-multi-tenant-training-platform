import os
import pymysql
from pymysql.cursors import DictCursor


def connect(database=None, cursorclass=DictCursor):
    return pymysql.connect(
        host=os.getenv('MYSQL_HOST', '127.0.0.1'),
        port=int(os.getenv('MYSQL_PORT', '3306')),
        unix_socket=os.getenv('MYSQL_SOCKET', '/tmp/mysql.sock') or None,
        user=os.getenv('MYSQL_USER', 'root'), password=os.getenv('MYSQL_PASSWORD', ''),
        database=database or os.getenv('MYSQL_DATABASE', 'certificate_admin'),
        charset='utf8mb4', cursorclass=cursorclass, autocommit=False,
        connect_timeout=5, read_timeout=55, write_timeout=15,
        init_command="SET time_zone = '+00:00'",
    )


DDL = [
    '''CREATE TABLE IF NOT EXISTS tenants (
       id BIGINT PRIMARY KEY, name VARCHAR(80) NOT NULL, timezone VARCHAR(80) NOT NULL
    ) ENGINE=InnoDB''',
    '''CREATE TABLE IF NOT EXISTS admins (
       id BIGINT PRIMARY KEY, tenant_id BIGINT NOT NULL, email VARCHAR(160) NOT NULL UNIQUE,
       UNIQUE(id, tenant_id), FOREIGN KEY (tenant_id) REFERENCES tenants(id)
    ) ENGINE=InnoDB''',
    '''CREATE TABLE IF NOT EXISTS courses (
       id BIGINT PRIMARY KEY, tenant_id BIGINT NOT NULL, title VARCHAR(160) NOT NULL,
       UNIQUE(id, tenant_id), FOREIGN KEY (tenant_id) REFERENCES tenants(id)
    ) ENGINE=InnoDB''',
    '''CREATE TABLE IF NOT EXISTS learners (
       id BIGINT PRIMARY KEY, tenant_id BIGINT NOT NULL, name VARCHAR(160) NOT NULL,
       UNIQUE(id, tenant_id), FOREIGN KEY (tenant_id) REFERENCES tenants(id)
    ) ENGINE=InnoDB''',
    '''CREATE TABLE IF NOT EXISTS enrollments (
       id BIGINT PRIMARY KEY, tenant_id BIGINT NOT NULL, course_id BIGINT NOT NULL,
       learner_id BIGINT NOT NULL, completed BOOLEAN NOT NULL,
       UNIQUE(id, tenant_id), UNIQUE(tenant_id, course_id, learner_id),
       FOREIGN KEY (course_id,tenant_id) REFERENCES courses(id,tenant_id),
       FOREIGN KEY (learner_id,tenant_id) REFERENCES learners(id,tenant_id)
    ) ENGINE=InnoDB''',
    '''CREATE TABLE IF NOT EXISTS certificates (
       id BIGINT AUTO_INCREMENT PRIMARY KEY, tenant_id BIGINT NOT NULL,
       enrollment_id BIGINT NOT NULL, serial_number VARCHAR(80) NOT NULL UNIQUE,
       issued_at DATETIME(6) NOT NULL, issue_date DATE NOT NULL,
       status ENUM('ACTIVE','REVOKED') NOT NULL DEFAULT 'ACTIVE', revoked_at DATETIME(6),
       UNIQUE(tenant_id,enrollment_id), UNIQUE(id,tenant_id),
       KEY list_date(tenant_id,issue_date,id),
       FOREIGN KEY (enrollment_id,tenant_id) REFERENCES enrollments(id,tenant_id)
    ) ENGINE=InnoDB''',
    '''CREATE TABLE IF NOT EXISTS operations (
       id BIGINT AUTO_INCREMENT PRIMARY KEY, tenant_id BIGINT NOT NULL, actor_id BIGINT NOT NULL,
       idempotency_key VARCHAR(128) NOT NULL, fingerprint CHAR(64) NOT NULL,
       status VARCHAR(24) NOT NULL, result JSON,
       UNIQUE(tenant_id,actor_id,idempotency_key),
       FOREIGN KEY (actor_id,tenant_id) REFERENCES admins(id,tenant_id)
    ) ENGINE=InnoDB''',
    '''CREATE TABLE IF NOT EXISTS audit_events (
       id BIGINT AUTO_INCREMENT PRIMARY KEY, tenant_id BIGINT NOT NULL,
       certificate_id BIGINT NOT NULL, actor_id BIGINT NOT NULL,
       action ENUM('ISSUED','REVOKED') NOT NULL, occurred_at DATETIME(6) NOT NULL,
       UNIQUE(certificate_id,action),
       FOREIGN KEY (certificate_id,tenant_id) REFERENCES certificates(id,tenant_id),
       FOREIGN KEY (actor_id,tenant_id) REFERENCES admins(id,tenant_id)
    ) ENGINE=InnoDB''',
]


def initialize():
    with connect() as db:
        with db.cursor() as c:
            for statement in DDL:
                c.execute(statement)
        db.commit()
