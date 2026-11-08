# Clean checkout verification

Implementation: `0e656c0a6515a3702fbbcaf01ce650518515f352`.
Supplemental verification date: 2026-11-08, Asia/Shanghai, beginning 15:26.
Platform: macOS, Python 3.15.2, MySQL 9.3.0, Node 26.13.0, npm 11.20.0.

## Preparation and actual commands

An independent local clone was created using git, with no venv, frontend dependencies, built assets
or environment file copied from the working checkout. Package manager download caches were allowed.
A new database was created with plain CREATE DATABASE (not IF NOT EXISTS), so an existing populated
database could not silently satisfy this check:

```sh
mysql -e 'CREATE DATABASE certificate_admin_clean_verify_20261108_1526 CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;'
git clone --no-hardlinks --branch codex/certificate-admin /Users/shikunli/Documents/ChatGPT/project1108 /private/tmp/certificate-admin-clean-20261108-1526
cd /private/tmp/certificate-admin-clean-20261108-1526
MYSQL_DATABASE=certificate_admin_clean_verify_20261108_1526 PORT=18020 npm_config_strict_ssl=false bash scripts/start.sh
```

The last command installed Python and frontend dependencies, built Vue, initialized schema and seeds,
and started the complete application on 18020. npm's temporary TLS bypass had been expressly approved
by the user. It does not persist configuration and was required by this machine's certificate issue.
The dedicated database is retained; no default application data was deleted or reset.

Against this instance:

```sh
MYSQL_DATABASE=certificate_admin_clean_verify_20261108_1526 BASE_URL=http://127.0.0.1:18020 .venv/bin/python scripts/startup_check.py
BASE_URL=http://127.0.0.1:18020 CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' PLAYWRIGHT_MODULE=/Users/shikunli/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright node scripts/browser-check.cjs
```

Both passed. The startup check took 0.080 seconds. The browser issued the fresh Safety 101 certificates,
reloaded the page and read Alex's detail from the database, with no page script errors.
Playwright was already provided by the desktop runtime; the module path is environment-specific and
not a production app dependency. Chrome was the existing installed browser.

The same clean clone then ran a server on 18021 against `certificate_admin_test` for the full API
acceptance suite. Its unit/transaction tests also passed (22 tests, no skips, 17.234 seconds).
An accidentally overlapping first acceptance run failed a global-count assertion due to the other
suite's writes. The failed run is preserved, and A1-A7 was rerun with no other mutating suite active.
The sequential rerun passed all seven cases: exports 1.194s/0.768s, concurrent list 0.558s.

## Evidence

- clean-checkout-startup.txt: dependency installation, frontend build, seed and server logs.
- clean-checkout-check.txt: bounded API/database startup check result.
- clean-checkout-browser.txt and .png: real browser write/read evidence from the clean instance.
- clean-checkout-tests.txt: all 22 tests passed, no skips.
- final-acceptance.json and final-acceptance-run.txt: final sequential A1-A7 results.
- final-acceptance-concurrent-interference.json and .txt: preserved failed validation attempt.

The clean clone's tracked files were clean before verification; the browser/suite then generated their
normal evidence outputs. The final supplemental commit changes documentation and export tooling only,
so the verified product implementation remains exactly the commit above. Temporary verification servers
are stopped after checks; the original application remains on port 8010.
