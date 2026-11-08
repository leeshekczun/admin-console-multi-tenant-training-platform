# Certificate Admin

Internal multi-tenant training certificate console built with Python/FastAPI, MySQL and Vue 3/Vite.
The user accepted the product and test milestone. This repository also records later, explicitly
approved documentation/evidence work outside the original 45-minute task window; see `docs/timing.md`.
No claim is made that the entire assessment submission, including independent written answers, is complete.

## Requirements and configuration

Tested environment: macOS, Python 3.15.2, MySQL 9.3.0, Node 26.13.0, npm 11.20.0.
Python code requires Python 3.11+. Direct dependencies are pinned in `requirements.txt`;
Vue 3.5.45, Vite 6.4.5 and plugin-vue 5.2.3 are pinned in `frontend/package.json` with a committed npm lockfile.
Python transitive dependencies are resolved during installation; the clean startup log records the installed versions.

MySQL must already be running. Create the application and isolated verification databases once:

```sh
mysql -e 'CREATE DATABASE IF NOT EXISTS certificate_admin CHARACTER SET utf8mb4; CREATE DATABASE IF NOT EXISTS certificate_admin_test CHARACTER SET utf8mb4;'
```

These two databases were created on the development machine. Demo/local configuration uses the
`root` MySQL account with an empty password through `/tmp/mysql.sock`; it is not a production setup.
Copy `.env.example` to `.env` if different configuration is needed. Never commit `.env`.
The scripts source `.env` as shell configuration: quote values containing shell-special characters.

| Variable | Default | Purpose |
| --- | --- | --- |
| MYSQL_SOCKET | /tmp/mysql.sock | Local MySQL socket; set empty to use TCP |
| MYSQL_HOST | 127.0.0.1 | TCP host |
| MYSQL_PORT | 3306 | TCP port |
| MYSQL_USER | root | Database account |
| MYSQL_PASSWORD | empty | Database password, supplied locally |
| MYSQL_DATABASE | certificate_admin | Database for this process |
| PORT | 8010 | Full application's HTTP port |
| BASE_URL | http://127.0.0.1:8010 for startup check; 8011 for acceptance | URL of the matching running instance |

## One-command startup and shutdown

From the repository root, this one command installs declared dependencies, creates tables, initializes
repeatable demo data, builds Vue, and starts the complete app:

```sh
bash scripts/start.sh
```

Open **http://127.0.0.1:8010**. FastAPI serves both `/api` and the built frontend.
Stop with **Ctrl-C** in the startup terminal. Logs are written to that terminal.
If port 8010 is occupied, set `PORT` and use the corresponding URL.

On the development machine npm's certificate chain was unavailable. The user authorized a temporary
bypass for public dependency installation. The exact command used for clean-checkout verification was:

```sh
MYSQL_DATABASE=certificate_admin_clean_verify_20261108_1526 PORT=18020 npm_config_strict_ssl=false bash scripts/start.sh
```

That separate database had first been created empty. No application data, `.venv`, `node_modules` or
built frontend was copied into the clean clone. The environment override is local to the command;
the repository does not persistently disable TLS verification. On machines with a valid CA chain,
use the standard startup command above. Installation requires network access or a populated package cache.

## Demo identities and data

No login UI is required. Choose Alice/East or Bob/West in the administrator selector.
Direct requests use `X-Actor: alice@east.test` or `X-Actor: bob@west.test`.
These are demo identities, not production authentication.

| Tenant | IANA timezone | Admin | Safety 101 course ID |
| --- | --- | --- | --- |
| East | Australia/Sydney | alice@east.test | 100 |
| West | Australia/Perth | bob@west.test | 200 |

Each tenant has a separate Alex Lee (completed), Jamie Chen (incomplete), Taylor Smith
(completed and already certified) and Morgan Park (completed). Both also have a First Aid course
(IDs 101/201, initially no enrollments). On a fresh database, Safety 101 issuance issues Alex and
Morgan, skips Jamie as incomplete, and skips Taylor as already certified.

Seeded certificates `DEMO-EAST-001` and `DEMO-WEST-001` share UTC timestamp
`2026-01-10T13:30:00Z`. Local displays are East `2026-01-11 00:30` and West `2026-01-10 21:30`.
Issuance and revocation audit events are visible in certificate detail.

Initialize schema and demo data without starting the app:

```sh
.venv/bin/python -m backend.seed
```

The seed uses repeat-safe insertion. It never resets statuses or removes records. After previous
issuance, eligible learners are already certified and will be skipped; revoked certificates are
also skipped and cannot be reissued. Use a newly created empty database for an untouched demo.
Schema initialization is version-one `CREATE TABLE IF NOT EXISTS`; no later-version upgrade migration
is claimed. No real user data is included.

## Verification commands

### Startup check

With the matching application running:

```sh
bash scripts/check.sh
```

The check has a 45-second total deadline and per-request timeouts. It checks configuration, required
tables, built frontend and API readiness, and verifies the API database matches its configured database.
It creates a uniquely named `Startup Check ...` course/enrollment, issues through the API, reads list/detail,
and checks exactly one issuance audit in MySQL. It retains isolated check records for inspection.
Failures exit nonzero and identify the failed step. Use the same `.env`/database and matching `BASE_URL`
as the server. Logs: `verification/startup-candidate.txt`, `verification/clean-checkout-check.txt`.

### Unit and controlled transaction tests

Database-free API units:

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_api_units.py' -v
```

All 22 tests, including five real-MySQL transaction tests:

```sh
MYSQL_DATABASE=certificate_admin_test .venv/bin/python -m backend.seed
MYSQL_DATABASE=certificate_admin_test .venv/bin/python -m unittest discover -s tests -v
```

No running server is needed; these use TestClient. The five integration tests skip unless the explicit
test database is selected. They create unique retained fixtures and never delete existing data.
Fault hooks wrap real cursors/connections, proving savepoint/full rollback and pre-commit lock behavior
on MySQL. The expected injected audit exception is logged before the corresponding test reports `ok`.
See `docs/test-coverage.md`, `verification/all-tests.txt`, and `verification/clean-checkout-tests.txt`.
Vue behavior has browser verification; no Vue component unit-test suite is claimed.

### A1-A7 automated reproduction

Start a separate instance against the isolated database in one terminal:

```sh
MYSQL_DATABASE=certificate_admin_test PORT=8011 bash scripts/start.sh
```

In another terminal, from the same checkout:

```sh
BASE_URL=http://127.0.0.1:8011 bash scripts/verify.sh
```

The command requires the running server to use `certificate_admin_test`. Do not run other mutating
test suites simultaneously against that database: the acceptance suite checks before/after counts.
It creates fresh course/learner fixtures, uses real HTTP requests and SQL state verification, and generates
its own explicit growth dataset. The script has a 180-second total deadline; individual exports must
finish within 60 seconds. Results are saved to `verification/acceptance.json` and printed to the terminal.

| Scenario | Reproduction performed by scripts/acceptance.py | Required result |
| --- | --- | --- |
| A1 tenant isolation | Bob directly requests an East certificate ID, revokes it, issues East course 100, and searches/exports East serials; compare database counts | Detail/revoke/bulk 404; list/export reveal no East rows; no new certificate, audit or operation |
| A2 retry safety | Eight simultaneous requests for one fresh course with one key, followed by two sequential retries; compare all responses and SQL | Same operation/result; one certificate per eligible enrollment; exactly one issuance audit each |
| A3 key misuse | Reuse that key for First Aid 101 and nonexistent course 999999; replay original request | Both changed courses return 409; database counts and original result unchanged |
| A4 learner outcomes | Fresh completed, incomplete and already-certified fixtures in one course | Two issued; incomplete and duplicate skipped with reasons |
| A5 DST/local date | Fetch list/detail and filtered CSV for each seeded DEMO certificate | East 2026-01-11 00:30, West 2026-01-10 21:30; local calendar dates in CSV |
| A6 growth/export | Generate 100,000 East rows with equal learner sort values, search Growth Learner, sort learner descending, export twice; request list while first export is open; compare CSV to ordered SQL | Exactly 100,000 matching East rows; both exports under 60s; byte-identical repeated order with ID tie-break; list succeeds during export |
| A7 revocation | Four simultaneous revokes of one active certificate, then repeat; inspect SQL and attempt issuance again with a new key | Exactly one status change and revocation audit; all later revokes unchanged; revoked enrollment skipped |

Focused A3 regression, without a running server:

```sh
MYSQL_DATABASE=certificate_admin_test .venv/bin/python scripts/check_key_misuse.py
```

This includes the user-reported missing replacement course and checks unused keys still return 404
for missing/foreign courses. Original reproduction/fix evidence: `verification/key-misuse-*.txt`.

### Generate 100,000 rows explicitly

Never part of default quick-start data initialization:

```sh
MYSQL_DATABASE=certificate_admin_test .venv/bin/python scripts/generate_100k.py
```

Run the seed first if that database is empty. The generator adds 100,000 East certificates and their
issuance audits in a dedicated `Export Growth Dataset` course, using `GROWTH-EAST-000000` through
`GROWTH-EAST-099999`. Each group of ten learners shares a name to exercise stable sorting.
Repeating it does not add duplicates. West and existing default demo records are unchanged.
To inspect this dataset in the UI, run a server with the same test database and select Alice.

## Actual results and evidence

The implementation verified from a clean local clone was `0e656c0a6515a3702fbbcaf01ce650518515f352`.
Subsequent supplemental changes affect documentation/evidence export tooling only.

| Check | Actual result | Evidence |
| --- | --- | --- |
| Original core API/database flow | Passed, every actual issuance has one audit | verification/first-chain.md |
| Browser issue/reload/detail | Passed | verification/browser-main.txt |
| Browser tenant switch, actual West issuance, revoke confirmation, loading/empty/error retry, CSV download | Passed | verification/browser-scenarios.txt |
| API units + controlled MySQL transactions | 22 passed, no skips | verification/all-tests.txt; verification/clean-checkout-tests.txt |
| Clean-clone install, empty-database initialization and startup | Passed | verification/clean-checkout-startup.txt; verification/clean-checkout.md |
| Clean-clone startup write/read check | Passed, 0.080s | verification/clean-checkout-check.txt |
| Clean-clone browser actual issuance/readback | Passed | verification/clean-checkout-browser.txt and .png |
| A1-A7 final sequential regression | All passed; 100k exports 1.194s/0.768s, concurrent list 0.558s | verification/final-acceptance.json; verification/final-acceptance-run.txt |
| A3 missing-course regression | Passed, 409; no writes or overwritten result | verification/key-misuse-after.txt; verification/key-misuse-http.txt |

An initial supplemental acceptance run was incorrectly scheduled alongside another mutating test suite;
its global count assertion failed due to the other suite's writes. The failure is retained as
`verification/final-acceptance-concurrent-interference.*`; the final acceptance run is sequential.
The earlier `verification/npm-audit.json` is a historical audit of old versions, not the final dependency
set. The recorded update to Vue/Vite reported zero vulnerabilities; production builds passed afterward.

## Architecture and limitations

`backend/main.py`: scoped API, issue/revoke transactions and streaming CSV. `backend/db.py`: schema and
connection setup. `backend/seed.py`: fixtures. `frontend/App.vue`: all product screens and state handling.
Issue payload: `{"course_id":100}` with `Idempotency-Key`; extra fields are rejected. Supported list/CSV
sorts: `learner_name`, `course_title`, `serial_number`, `issue_date`, `status`; directions `asc`/`desc`.
Search matches learner names or serial numbers literally. List uses page/page_size (1..100 rows/page).
CSV exports all matching records, not just the displayed page. All sort ties use certificate ID ascending.

Certificate/audit writes commit atomically. Uniqueness protects enrollments and audit actions.
A coarse tenant-row lock serializes bulk operations across processes; same-key callers wait for the
committed result. An existing key's fingerprint is checked before looking up a replacement course.
Revocation locks the certificate row. UTC timestamps plus materialized tenant-local issue dates use IANA DST.
CSV uses a server-side cursor in bounded batches on an independent connection; no in-memory 100k store.

Performance results are for the documented local machine, not a guarantee for arbitrary hosts.
There is no schema evolution system, production authentication, cloud deployment, notifications or
unrelated functionality. The requirement excludes those features. The browser's missing favicon produces
an incidental 404; it does not affect application flows and no favicon feature is added.

## Submission completeness

See `COMPLETENESS.md`, `ai/session-index.csv`, `ai/decision-log.md`, and `docs/ai-export-index.md`.
Original assignment and instructions are in `docs/`; native session logs preserve original language.
All discovered project-bound native sessions are indexed, including independent review.

`written-answers.md` exists on the existing remote main branch and is preserved unchanged when preparing
this branch for a PR. Its content is not read, drafted, edited or reviewed by this agent. Section 6
completion and compliance remain the candidate's responsibility; this agent does not certify them.
The complete assessment submission therefore remains pending the candidate's independent work and
final packaging/submission decision. No submission email has been sent.

### Outstanding items at supplemental handoff

| Item | Actual status / limitation |
| --- | --- |
| Independent written answers | `written-answers.md` exists on remote main and is preserved unchanged. This agent has not read or reviewed it and does not certify Section 6 completion. |
| Original time-limit compliance | Supplemental verification/documentation was explicitly approved after the original 45-minute hard stop. A complete on-time assessment submission is not claimed. |
| Pull request and merge | Requested by the user but not yet completed at this documentation cutoff. The remote has no `master`; the user approved `main` as the target. SSH push works, but no GitHub CLI/token is configured and browser control timed out. PR creation needs authenticated GitHub API or browser access. The user will perform the merge; this agent will not merge. No PR or merge success is claimed. |
| Final submission email | Not sent; no email-sending instruction has been given. |
| Native log after export cutoff | Final packaging, push/PR/merge attempts and final handoff after the declared cutoff cannot be inside that same snapshot. The index states its exact cutoff; git/PR records identify later packaging. |
| Other AI tools unknown to this agent | All three discovered local project Codex sessions are included. Any additional off-machine/tool interactions require candidate disclosure and their original export. |

The README reproduction instructions, explicit 100,000-row command, completeness declaration,
multi-session evidence and clean-checkout verification have been supplied in this supplemental work.
Those are no longer listed as missing. Details and artifact paths are in `COMPLETENESS.md`.
