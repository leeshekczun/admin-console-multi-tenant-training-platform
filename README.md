# Certificate Admin

Internal multi-tenant training certificate console. Python + FastAPI, MySQL, Vue 3 + Vite.
Development in progress: acceptance results and remaining work are not yet final.

## Quick start

Prerequisites: local MySQL running, Python 3.11+ (tested 3.15.2), Node (tested 26.13.0), npm 11.20.0.
MySQL tested: 9.3.0. Fixed direct dependency versions: `requirements.txt`, `frontend/package.json`.

Create a database once if not already present (the development machine already has both):

```sh
mysql -e 'CREATE DATABASE IF NOT EXISTS certificate_admin CHARACTER SET utf8mb4; CREATE DATABASE IF NOT EXISTS certificate_admin_test CHARACTER SET utf8mb4;'
```

Default connection: local socket `/tmp/mysql.sock`, current demo configuration uses user `root`
and an empty password. Configure your own credentials through `.env` copied from `.env.example`.
Never commit `.env`. For TCP use an empty `MYSQL_SOCKET` and set `MYSQL_HOST`/`MYSQL_PORT`.

One-command installation, repeatable schema/demo initialization, frontend build and complete app startup:

```sh
bash scripts/start.sh
```

Open http://127.0.0.1:8010. Stop with Ctrl-C. Logs are on the server terminal.
No login UI: choose a demo administrator. API header: `X-Actor: alice@east.test` or `bob@west.test`.
The identities are a demo mechanism, not production authentication.

## First demonstration

1. Select Alice (East), choose Safety 101, click Issue certificates.
2. Alex Lee and Morgan Park are issued; Jamie Chen is skipped as incomplete; Taylor Smith is already certified.
3. Refresh/search the certificate list and view a certificate. Changes persist in MySQL.
4. Select Bob (West) to see only West data, including a separate Safety 101 and Alex Lee.
5. View the seeded Taylor certificate: East displays 2026-01-11 00:30, West displays 2026-01-10 21:30.

Seed repeats do not remove, reset or duplicate existing certificates. It does not reissue revoked certificates.
Reinitialize demo schema/data without starting the server: `.venv/bin/python -m backend.seed`.

## Architecture and boundaries

`backend/main.py`: actor context, scoped API queries, issue/revoke transactions and CSV.
`backend/db.py`: schema and connection configuration. `backend/seed.py`: repeatable fixtures.
`frontend/App.vue`: list, actor selection, issue outcomes, detail, revoke confirmation and CSV.
Certificate changes and audit events commit atomically. MySQL unique constraints protect each enrollment
and audit action. A tenant row lock serializes bulk operations across processes; repeated keys return
the saved response and different payloads return 409. Locks are intentionally coarse for this small console.
UTC timestamps and materialized tenant-local issue dates use IANA zoneinfo, including DST.
Sort ties always use certificate ID ascending. CSV uses the current search/sort over all matching rows,
not only the visible page; server-side cursors stream bounded batches on an independent connection.

## Verification and completeness

Run the bounded startup check against the running application:

```sh
bash scripts/check.sh
```

This checks configuration, required tables, built frontend and API readiness, then issues and reads
one isolated `Startup Check ...` record and verifies its database audit. It retains that clearly named
record for inspection. Total timeout is 45 seconds; a failure exits nonzero and names the step.
First run passed in 0.073 seconds. Browser issuance, reload and detail passed; evidence is in `verification/`.

A1-A7 passed on the local isolated test instance; results are in `verification/acceptance.json`
and `verification/acceptance-run.txt`. The 100,000-row generator is `scripts/generate_100k.py`;
it is deliberately excluded from quick-start initialization. Additional browser scenarios are recorded
in `verification/browser-scenarios.txt`. The current candidate startup check is in
`verification/startup-candidate.txt`.

Vue and Vite were updated to 3.5.45 and 6.4.5 using the npm audit recommended fixes;
installation reported zero vulnerabilities afterward. `verification/npm-audit.json` is the historical
audit of the previous dependency versions, retained as evidence of the correction.

Remaining delivery work: full A1-A7 reproduction instructions, clean-checkout one-command startup
verification, final AI export/index and decision-log reconciliation, and `COMPLETENESS.md`.
The current native AI export is a point-in-time snapshot, not a claim of final completeness.
User-reported A3 correction: an already-used key with a different `course_id` now returns 409
even when the replacement course does not exist. Existing-key fingerprint comparison precedes
course lookup. Regression evidence is in `verification/key-misuse-before.txt` and
`verification/key-misuse-after.txt`; the original result and database counts remain unchanged.
Section 6 answers must be supplied independently by the candidate; `written-answers.md` is not supplied.
Original assignment: `docs/assessment.pdf`. Native AI evidence: `ai/sessions/`, indexes in `ai/` and `docs/`.
No cloud deployment, production authentication, notifications or unrelated features are included.
