# Delivery card and short design

User authorized start: 2026-11-08 14:31:57 Asia/Shanghai (first measured clock).
Total sitting deadline: 15:31:57. Implementation must also stop at first task commit +45 min.
Stack: Python/FastAPI, local MySQL, Vue 3/Vite. No cloud deployment or production authentication.
Branch: codex/certificate-admin. Remote: git@github.com:leeshekczun/admin-console-multi-tenant-training-platform.git.
Databases created: certificate_admin and certificate_admin_test (isolated verification).

Priority: actor -> course -> issue -> persisted certificate/audit -> list/detail; then retries,
revocation, searching/sorting/pagination, tenant time, export and A1-A7 verification.
No revoked certificate reissue. Local calendar date sort with certificate ID tie-break.
UTC storage, Python zoneinfo conversion. Actor header is a demo identity, not production auth.
MySQL uniqueness and transactions enforce issuance/audit and idempotency. Streaming CSV with
stable sorting and separate request connections. No external services or caching.

Proposed gates: first chain +15 min, remaining implementation +28, candidate +36,
implementation lock +40, final commit target +43, hard stop +45.
Every closed slice is committed and pushed. Missing requirements are declared, never passed.
Verification: browser real write/read, direct API tenant/retry/audit checks, 100k export twice
with concurrent list (most expensive check, target <=3 min total).
No alternative database or reduced acceptance authorized. Time shortfall is recorded in README.

Required artifacts: README, repeatable demo seed, startup check, native AI JSONL + indexes +
decision log, COMPLETENESS. Original assignment and playbook preserved in docs.
Section 6 written answers must be independently written by the candidate; AI will not write them.
Dependencies and MySQL version are recorded in README as actually tested.

Preparation: MySQL 9.3.0 reachable, two databases created, GitHub SSH reachable.
Native export test: session JSONL copied and parsed; includes messages, calls and outputs.
No manual summary is substituted. Export updates will stop before final handoff and state cutoff.
